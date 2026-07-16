"""
data_pipeline.py -- ingesta de velas OHLC (1H/4H/1D) desde un exchange
(Binance u otro compatible con ccxt) hacia la tabla velas_cripto, que
TradingLogic (src/trading/crypto_trader_agent.py) necesita para dejar de
devolver ESTADO: ESPERA por falta de datos.

Usa el endpoint público de mercado (fetch_ohlcv) -- no requiere API key ni
autenticación, solo datos de velas ya públicos.

REQUISITO PREVIO, fuera del alcance de este script: la tabla velas_cripto
todavía no existe en Supabase (verificado 2026-07-16, error PGRST205 "Could
not find the table"). Hay que correr sql/create_velas_cripto.sql en el SQL
Editor de Supabase (con permisos de owner) antes de que este pipeline pueda
insertar nada -- la key configurada en .env es 'anon' y no puede hacer DDL.
Una vez creada la tabla, conviene volver a correr este script con --limite 5
para confirmar que el INSERT no está bloqueado por RLS (ya vimos que esa
misma key sí tiene DELETE bloqueado en precios_serviu).

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

CORE_PATH = Path("/home/ibar/Proyectos/DepaFix")
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
    """Convierte el formato ccxt ([ts_ms, open, high, low, close, volume])
    al esquema exacto que espera velas_cripto / TradingLogic._obtener_velas:
    tiempo, open, high, low, close, volume."""
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
            self.db = DatabaseManager.get_client()
        except Exception as e:
            logger.error("No se pudo inicializar el cliente de Supabase: %s", e)

    def _guardar_filas(self, filas):
        """Upsert por lotes (idempotente: activo+temporalidad+tiempo es
        UNIQUE en velas_cripto, así que correr el pipeline dos veces no
        duplica). Cada lote en su propio try/except."""
        if not self.db or not filas:
            return 0
        guardadas = 0
        for i in range(0, len(filas), TAMANO_LOTE_INSERT):
            lote = filas[i:i + TAMANO_LOTE_INSERT]
            try:
                self.db.table(TABLA_VELAS).upsert(lote, on_conflict="activo,temporalidad,tiempo").execute()
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
