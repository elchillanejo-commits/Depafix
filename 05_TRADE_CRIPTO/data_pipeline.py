"""
data_pipeline.py -- ingesta de velas OHLC (1H/4H/1D) desde un exchange
(Binance u otro compatible con ccxt) hacia la tabla velas_cripto, que
TradingLogic (src/trading/crypto_trader_agent.py) necesita para dejar de
devolver ESTADO: ESPERA por falta de datos.

Usa el endpoint público de mercado (fetch_ohlcv) -- no requiere API key ni
autenticación, solo datos de velas ya públicos.

REQUISITOS PREVIOS, fuera del alcance de este script:
  1. La tabla velas_cripto todavía no existe en Supabase (verificado
     2026-07-16, error PGRST205 "Could not find the table"). Correr
     01_SERVIU/create_velas_cripto.sql en el SQL Editor de Supabase (permisos de
     owner) -- la key 'anon' de .env no puede hacer DDL.
  2. Ese SQL deja RLS activado SIN policy para anon a propósito (la anon key
     es pública por diseño; no debe poder escribir ni leer esta tabla). Este
     pipeline escribe con SUPABASE_SERVICE_ROLE_KEY (service_role, bypassea RLS)
     -- agregar esa variable a .env con el valor del dashboard de Supabase
     (Settings > API > service_role) antes de correr esto. Sin ella, falla
     explícito en el log en vez de chocar en silencio contra RLS.

Uso:
    python3 src/trading/data_pipeline.py [--exchange binance] [--pares BTC/USDT,ETH/USDT] [--limite 500]
"""
import argparse
import logging
import random
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

import ccxt

# Relativa a este archivo, no al home del dev -- tiene que resolver igual en
# local y dentro del contenedor de Railway (ver mismo fix en
# trading_orchestrator.py). core/ vive en DepaFix/procurador/core
# (02_PROCURADOR fue renombrado ahi, commit 10462fe).
CORE_PATH = Path(__file__).resolve().parent.parent / "procurador"
if str(CORE_PATH) not in sys.path:
    sys.path.insert(0, str(CORE_PATH))

from core.db_manager import DatabaseManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

TABLA_VELAS = "velas_cripto"
PARES_DEFAULT = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT"]
# Nuestro esquema usa '1H'/'4H'/'1D' (igual que TradingLogic); ccxt pide su
# propia notación de timeframe.
TEMPORALIDADES = {"1H": "1h", "4H": "4h", "1D": "1d"}
LIMITE_DEFAULT = 500
MAX_REINTENTOS = 5
BACKOFF_BASE_SEG = 2
TAMANO_LOTE_INSERT = 500


def _con_reintentos(func, *args, **kwargs):
    """Backoff exponencial con jitter ante rate limit / caídas de red del
    exchange. Después de MAX_REINTENTOS, propaga la excepción para que el
    llamador la loguee y siga con la siguiente combinación par/temporalidad
    en vez de abortar todo el pipeline."""
    ultimo_error = None
    for intento in range(MAX_REINTENTOS):
        try:
            return func(*args, **kwargs)
        except (ccxt.RateLimitExceeded, ccxt.DDoSProtection, ccxt.ExchangeNotAvailable, ccxt.NetworkError) as e:
            ultimo_error = e
            espera = BACKOFF_BASE_SEG * (2 ** intento) + random.uniform(0, 1)
            logger.warning(
                "Rate limit / red (intento %d/%d): %s. Reintentando en %.1fs.",
                intento + 1, MAX_REINTENTOS, e, espera,
            )
            time.sleep(espera)
    raise ultimo_error


def _velas_a_filas(ohlcv, activo, temporalidad):
    """Convierte el formato ccxt ([ts_ms, open, high, low, close, volume]) a
    la representacion interna que usan TradingLogic/RiskManager en todo el
    resto del pipeline (activo, temporalidad, tiempo, open, high, low,
    close, volume). Esto NO es el esquema de la tabla velas_cripto -- ver
    _fila_a_db()/_fila_desde_db() para esa traduccion, aislada aca a
    proposito para no tener que tocar TradingLogic/RiskManager."""
    filas = []
    for ts_ms, o, h, l, c, v in ohlcv:
        filas.append({
            "activo": activo,
            "temporalidad": temporalidad,
            "tiempo": datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).isoformat(),
            "open": o,
            "high": h,
            "low": l,
            "close": c,
            "volume": v,
        })
    return filas


def _fila_a_db(fila):
    """Traduce la representacion interna (activo/temporalidad/tiempo/open/
    high/low/close/volume) al esquema real y vivo de velas_cripto en
    Supabase (par/intervalo/timestamp/apertura/maximo/minimo/cierre/
    volumen -- confirmado via el schema de PostgREST, create_velas_cripto.sql
    quedo desactualizado)."""
    return {
        "par": fila["activo"],
        "intervalo": fila["temporalidad"],
        "timestamp": fila["tiempo"],
        "apertura": fila["open"],
        "maximo": fila["high"],
        "minimo": fila["low"],
        "cierre": fila["close"],
        "volumen": fila["volume"],
    }


def _fila_desde_db(row):
    """Inverso de _fila_a_db(): de una fila de Supabase de vuelta a la
    representacion interna que esperan TradingLogic/RiskManager."""
    return {
        "activo": row.get("par"),
        "temporalidad": row.get("intervalo"),
        "tiempo": row.get("timestamp"),
        "open": row.get("apertura"),
        "high": row.get("maximo"),
        "low": row.get("minimo"),
        "close": row.get("cierre"),
        "volume": row.get("volumen"),
    }


class PipelineVelas:
    def __init__(self, exchange_id="binance", pares=None, temporalidades=None, limite=LIMITE_DEFAULT):
        self.pares = pares or PARES_DEFAULT
        self.temporalidades = temporalidades or list(TEMPORALIDADES.keys())
        self.limite = limite
        self.exchange = None
        self.db = None

        try:
            clase_exchange = getattr(ccxt, exchange_id)
            self.exchange = clase_exchange({"enableRateLimit": True})
        except Exception as e:
            logger.error("No se pudo inicializar el exchange '%s': %s", exchange_id, e)

        try:
            # service_role, no anon: velas_cripto tiene RLS activado sin
            # policy para anon a propósito (ver 01_SERVIU/create_velas_cripto.sql)
            # para que la anon key -- pública por diseño -- no pueda escribir
            # ni borrar. Si SUPABASE_SERVICE_ROLE_KEY no está configurada, esto
            # falla fuerte y explícito en vez de degradar en silencio a un
            # cliente que va a chocar con RLS en cada INSERT.
            self.db = DatabaseManager.get_service_client()
        except Exception as e:
            logger.error("No se pudo inicializar el cliente de Supabase (service_role): %s", e)

    def _guardar_filas(self, filas):
        """Upsert por lotes (idempotente: activo+temporalidad+tiempo es
        UNIQUE en velas_cripto, así que correr el pipeline dos veces no
        duplica). Cada lote en su propio try/except."""
        if not self.db or not filas:
            return 0
        guardadas = 0
        for i in range(0, len(filas), TAMANO_LOTE_INSERT):
            lote = filas[i:i + TAMANO_LOTE_INSERT]
            lote_db = [_fila_a_db(f) for f in lote]
            try:
                self.db.table(TABLA_VELAS).upsert(lote_db, on_conflict="par,intervalo,timestamp").execute()
                guardadas += len(lote)
            except Exception as e:
                logger.error(
                    "Fallo guardando lote de %d velas (%s, filas %d-%d): %s",
                    len(lote), filas[0]["activo"], i, i + len(lote), e,
                )
        return guardadas

    def _ingestar_una_combinacion(self, activo, temporalidad):
        if not self.exchange:
            return 0
        timeframe_ccxt = TEMPORALIDADES[temporalidad]
        try:
            ohlcv = _con_reintentos(self.exchange.fetch_ohlcv, activo, timeframe=timeframe_ccxt, limit=self.limite)
        except Exception as e:
            logger.error("Fallo definitivo trayendo %s %s tras %d reintentos: %s", activo, temporalidad, MAX_REINTENTOS, e)
            return 0

        if not ohlcv:
            logger.warning("El exchange devolvió 0 velas para %s %s.", activo, temporalidad)
            return 0

        filas = _velas_a_filas(ohlcv, activo, temporalidad)
        guardadas = self._guardar_filas(filas)
        logger.info("%s %s: %d velas traídas, %d guardadas.", activo, temporalidad, len(ohlcv), guardadas)
        return guardadas

    def obtener_velas_para_analisis(self, activo: str, temporalidad: str, limite: int = 100):
        """Lee velas ya guardadas en velas_cripto (con self.db, el mismo
        cliente service_role que usa el resto de la clase -- no el cliente
        anon, que este archivo bloquea a propósito vía RLS). Si Supabase
        falla o todavía no tiene datos para ese par/temporalidad, cae a
        traerlas directo del exchange (sin guardarlas -- para eso está
        ejecutar()/_ingestar_una_combinacion). Devuelve siempre una lista
        (vacía si no hay datos ni exchange disponible), nunca lanza."""
        if self.db:
            try:
                resp = (
                    self.db.table(TABLA_VELAS)
                    .select("*")
                    .eq("par", activo)
                    .eq("intervalo", temporalidad)
                    .order("timestamp", desc=True)
                    .limit(limite)
                    .execute()
                )
                if resp.data:
                    return [_fila_desde_db(row) for row in resp.data]
            except Exception as e:
                logger.error("Fallo leyendo velas de Supabase para %s %s: %s", activo, temporalidad, e)

        if not self.exchange:
            return []
        timeframe_ccxt = TEMPORALIDADES.get(temporalidad)
        if not timeframe_ccxt:
            logger.error("Temporalidad desconocida '%s' -- no se puede consultar al exchange.", temporalidad)
            return []
        try:
            ohlcv = _con_reintentos(self.exchange.fetch_ohlcv, activo, timeframe=timeframe_ccxt, limit=limite)
        except Exception as e:
            logger.error("Fallo trayendo velas directo del exchange para %s %s: %s", activo, temporalidad, e)
            return []
        return _velas_a_filas(ohlcv, activo, temporalidad)

    def ejecutar(self):
        """Nunca lanza excepción hacia afuera: cada combinación par/temporalidad
        se procesa en su propio try/except, igual que trade_agent.py con sus
        ítems -- un símbolo caído no debe frenar al resto."""
        total_guardadas = 0
        for activo in self.pares:
            for temporalidad in self.temporalidades:
                try:
                    total_guardadas += self._ingestar_una_combinacion(activo, temporalidad)
                except Exception:
                    logger.error(
                        "Excepción no controlada ingiriendo %s %s:\n%s",
                        activo, temporalidad, traceback.format_exc(),
                    )
                    continue
        logger.info(
            "Pipeline de velas finalizado. %d pares x %d temporalidades procesadas, %d velas guardadas en total.",
            len(self.pares), len(self.temporalidades), total_guardadas,
        )
        return total_guardadas


def main():
    parser = argparse.ArgumentParser(description="Ingesta de velas OHLC hacia velas_cripto")
    parser.add_argument("--exchange", default="binance", help="Exchange soportado por ccxt (binance, bybit, ...)")
    parser.add_argument("--pares", default=",".join(PARES_DEFAULT), help="Lista separada por comas, ej. BTC/USDT,ETH/USDT")
    parser.add_argument("--temporalidades", default=",".join(TEMPORALIDADES.keys()))
    parser.add_argument("--limite", type=int, default=LIMITE_DEFAULT, help="Velas a traer por combinación par/temporalidad")
    args = parser.parse_args()

    pipeline = PipelineVelas(
        exchange_id=args.exchange,
        pares=[p.strip() for p in args.pares.split(",") if p.strip()],
        temporalidades=[t.strip() for t in args.temporalidades.split(",") if t.strip()],
        limite=args.limite,
    )
    pipeline.ejecutar()


if __name__ == "__main__":
    main()
