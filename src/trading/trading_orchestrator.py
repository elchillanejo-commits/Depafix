"""
trading_orchestrator.py -- orquesta ingesta de velas, generacion de senal
(SignalEngine sobre TradingLogic, ver crypto_trader_agent.py) y gestion de
riesgo (RiskManager: circuit breaker + filtro de volatilidad) antes de dejar
auditoria en operaciones_ejecutadas.

MODO SIMULACION UNICAMENTE: no existe en este repo ningun codigo que coloque
ordenes reales en un exchange (create_order de ccxt no se usa en ningun
lado). Este orquestador genera senales, las audita con un hash SHA-256 del
estado de mercado que las motivo, y siempre guarda ejecutada=False. Conectar
esto a ejecucion real de ordenes es un paso separado y deliberado, fuera del
alcance de este archivo.

Uso:
    python3 src/trading/trading_orchestrator.py --activos BTC/USDT,ETH/USDT --intervalo 60
    python3 src/trading/trading_orchestrator.py --una-vez  # un solo ciclo, para cron/testing
"""
import argparse
import functools
import hashlib
import json
import logging
import random
import sys
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import numpy as np

CORE_PATH = Path(__file__).resolve().parent.parent.parent
if str(CORE_PATH) not in sys.path:
    sys.path.insert(0, str(CORE_PATH))

from core.db_manager import DatabaseManager
from src.trading.data_pipeline import PipelineVelas, PARES_DEFAULT
from src.trading.crypto_trader_agent import TradingLogic

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

TABLA_OPERACIONES = "operaciones_ejecutadas"
MAX_LATENCIA_SEG = 0.5
MAX_REINTENTOS = 5
BACKOFF_BASE_SEG = 2
DRAWDOWN_MAX_PCT = 2.0
VENTANA_VOLATILIDAD = 20

# Pool aparte para el decorador de latencia maxima: las llamadas de red que
# envuelve (httpx via supabase-py, ccxt) son sincronicas y no se pueden
# cancelar de forma preventiva a mitad de un socket. Usar .result(timeout=)
# deja de esperar y trata el intento como fallido -- que es la semantica
# util aca ("no bloquees el ciclo mas de 500ms"), aunque el hilo de fondo
# pueda seguir corriendo hasta que la llamada subyacente resuelva sola.
_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="trading-net")


class RedFailSafeError(RuntimeError):
    """Senal de desconexion segura: se agotaron los reintentos o se excedio
    la latencia maxima. El llamador debe tratarlo como "no operar este
    ciclo", nunca reintentar por su cuenta por fuera del decorador."""


def _con_latencia_maxima(func: Callable, segundos: float) -> Callable:
    @functools.wraps(func)
    def envoltura(*args, **kwargs):
        futuro = _executor.submit(func, *args, **kwargs)
        try:
            return futuro.result(timeout=segundos)
        except FutureTimeoutError:
            raise RedFailSafeError(
                f"{func.__name__} excedio latencia maxima de {segundos * 1000:.0f}ms"
            ) from None
    return envoltura


def red_segura(max_reintentos: int = MAX_REINTENTOS, backoff_base: float = BACKOFF_BASE_SEG,
               latencia_max: float = MAX_LATENCIA_SEG) -> Callable:
    """Decorador para toda llamada de red (Supabase, exchange): cada intento
    esta acotado a latencia_max segundos: si lo excede o lanza excepcion,
    reintenta con backoff exponencial + jitter hasta max_reintentos veces.
    Agotados los reintentos, levanta RedFailSafeError -- fail-safe explicito
    en vez de dejar que el error de red se propague crudo o, peor, que el
    llamador seagote reintentando indefinidamente."""
    def decorador(func: Callable) -> Callable:
        func_acotado = _con_latencia_maxima(func, latencia_max)

        @functools.wraps(func)
        def envoltura(*args, **kwargs):
            ultimo_error = None
            for intento in range(max_reintentos):
                try:
                    return func_acotado(*args, **kwargs)
                except Exception as e:
                    ultimo_error = e
                    espera = backoff_base * (2 ** intento) + random.uniform(0, 1)
                    logger.warning(
                        "%s: fallo de red (intento %d/%d): %s. Reintentando en %.1fs.",
                        func.__name__, intento + 1, max_reintentos, e, espera,
                    )
                    time.sleep(espera)
            logger.critical(
                "%s: agotados %d reintentos, desconexion segura (fail-safe).",
                func.__name__, max_reintentos,
            )
            raise RedFailSafeError(f"{func.__name__} agoto reintentos") from ultimo_error
        return envoltura
    return decorador


class RiskManager:
    """Circuit breaker por drawdown de sesion + filtro de volatilidad por
    correlacion precio/volumen. No conoce nada de Supabase ni de exchanges:
    solo decide si es seguro dejar pasar una senal, a partir del estado de
    capital que el orquestador le reporte y de las velas que se le pasen."""

    def __init__(self, capital_inicial: float, drawdown_max_pct: float = DRAWDOWN_MAX_PCT):
        if capital_inicial <= 0:
            raise ValueError("capital_inicial debe ser > 0 para calcular drawdown")
        self.capital_pico = capital_inicial
        self.capital_actual = capital_inicial
        self.drawdown_max_pct = drawdown_max_pct
        self._suspendido = False
        self._motivo_suspension: Optional[str] = None

    def actualizar_capital(self, capital_actual: float) -> None:
        self.capital_actual = capital_actual
        self.capital_pico = max(self.capital_pico, capital_actual)

    def circuit_breaker(self) -> bool:
        """True si es seguro operar. Una vez que se suspende por drawdown,
        se mantiene suspendido hasta un reset() explicito: un circuit
        breaker que se reactiva solo en el proximo ciclo (por ejemplo si el
        capital se recupera) no protege nada -- el punto es forzar revision
        humana antes de seguir."""
        if self._suspendido:
            return False
        drawdown_pct = (self.capital_pico - self.capital_actual) / self.capital_pico * 100
        if drawdown_pct >= self.drawdown_max_pct:
            self._suspendido = True
            self._motivo_suspension = f"drawdown {drawdown_pct:.2f}% >= limite {self.drawdown_max_pct}%"
            logger.critical("CIRCUIT BREAKER activado: %s. Operaciones suspendidas.", self._motivo_suspension)
            return False
        return True

    def reset(self) -> None:
        logger.warning("Circuit breaker reseteado manualmente (motivo previo: %s).", self._motivo_suspension)
        self._suspendido = False
        self._motivo_suspension = None
        self.capital_pico = self.capital_actual

    @staticmethod
    def volatility_filter(velas: List[Dict[str, Any]], ventana: int = VENTANA_VOLATILIDAD) -> bool:
        """True solo si hay correlacion positiva entre volumen y variacion
        de precio en la ventana reciente: exige que el movimiento este
        respaldado por volumen real, no ruido de baja liquidez. Sin
        suficientes velas, o con precio/volumen sin varianza (correlacion
        indefinida), se rechaza por defecto -- sin evidencia de liquidez no
        hay confirmacion."""
        if len(velas) < ventana + 1:
            logger.warning("volatility_filter: velas insuficientes (%d < %d), rechazado.", len(velas), ventana + 1)
            return False
        recientes = velas[-(ventana + 1):]
        cambios_precio = np.abs(np.diff([v["close"] for v in recientes]))
        volumenes = np.array([v.get("volume") or 0.0 for v in recientes[1:]])
        if np.std(cambios_precio) == 0 or np.std(volumenes) == 0:
            logger.warning("volatility_filter: precio o volumen sin varianza, correlacion indefinida, rechazado.")
            return False
        correlacion = float(np.corrcoef(cambios_precio, volumenes)[0, 1])
        aprobado = correlacion > 0
        logger.info("volatility_filter: correlacion precio/volumen = %.3f (%s).",
                    correlacion, "aprobado" if aprobado else "rechazado")
        return aprobado


class SignalEngine:
    """Envoltorio sobre TradingLogic (crypto_trader_agent.py): la logica de
    Price Action (Fibonacci, FVG, Order Blocks, confluencia) ya vive ahi;
    este motor no la duplica, solo le da la interfaz que usa el
    orquestador."""

    def __init__(self):
        self._logic = TradingLogic()

    def generar_senal(self, velas: List[Dict[str, Any]]) -> Dict[str, Any]:
        return self._logic.analizar(velas)


class TradingOrchestrator:
    def __init__(self, exchange_id: str = "binance", pares: Optional[List[str]] = None,
                 capital_inicial: float = 1000.0):
        self.pares = pares or PARES_DEFAULT
        self.pipeline = PipelineVelas(exchange_id=exchange_id, pares=self.pares)
        self.signal_engine = SignalEngine()
        self.risk_manager = RiskManager(capital_inicial=capital_inicial)
        self._db = None
        try:
            # Mismo cliente cacheado (DatabaseManager._service_client) que ya
            # usa PipelineVelas -- no abre una conexion nueva, get_service_client()
            # devuelve la instancia existente si ya fue creada.
            self._db = DatabaseManager.get_service_client()
        except Exception as e:
            logger.error("No se pudo inicializar Supabase (service_role) para auditoria: %s", e)

    @red_segura()
    def fetch_market_data(self, activo: str, temporalidad: str = "1H", limite: int = 100) -> List[Dict[str, Any]]:
        velas = self.pipeline.obtener_velas_para_analisis(activo, temporalidad, limite)
        if not velas:
            raise RedFailSafeError(f"Sin velas disponibles para {activo} {temporalidad}")
        return velas

    @staticmethod
    def _hash_estado_mercado(velas: List[Dict[str, Any]], senal: Dict[str, Any]) -> str:
        """SHA-256 sobre una representacion canonica (JSON con claves
        ordenadas) de las ultimas velas usadas + la senal generada. Deja
        trazabilidad verificable de que datos exactos motivaron la orden sin
        tener que guardar el historial completo de velas en cada fila de
        auditoria."""
        payload = {
            "velas": velas[-5:],
            "senal": {k: v for k, v in senal.items() if k != "fibonacci"},
        }
        payload_json = json.dumps(payload, sort_keys=True, default=str)
        return hashlib.sha256(payload_json.encode("utf-8")).hexdigest()

    @red_segura()
    def _registrar_operacion(self, fila: Dict[str, Any]) -> None:
        if not self._db:
            raise RedFailSafeError("Cliente Supabase (service_role) no disponible para auditoria")
        self._db.table(TABLA_OPERACIONES).insert(fila).execute()

    def procesar_activo(self, activo: str, temporalidad: str = "1H") -> Optional[Dict[str, Any]]:
        if not self.risk_manager.circuit_breaker():
            logger.warning("%s: circuit breaker activo, se omite el ciclo.", activo)
            return None

        try:
            velas = self.fetch_market_data(activo, temporalidad)
        except RedFailSafeError as e:
            logger.critical("%s: fail-safe de red en fetch_market_data: %s. Desconectando de forma segura.", activo, e)
            return None

        senal = self.signal_engine.generar_senal(velas)
        logger.info("%s -> %s (%s)", activo, senal.get("senal"), senal.get("motivo"))

        if senal.get("senal") not in ("COMPRA", "VENTA"):
            return senal

        if not self.risk_manager.volatility_filter(velas):
            logger.warning("%s: senal %s rechazada por volatility_filter (volumen no confirma el movimiento).",
                           activo, senal.get("senal"))
            return senal

        fila = {
            "activo": activo,
            "temporalidad": temporalidad,
            "senal": senal.get("senal"),
            "precio_entrada": senal.get("precio_actual"),
            "precio_salida": None,
            "cantidad": None,
            "motivo": senal.get("motivo"),
            "hash_control": self._hash_estado_mercado(velas, senal),
            "ejecutada": False,  # simulacion siempre: no hay integracion de ordenes reales en este repo
        }

        try:
            self._registrar_operacion(fila)
            logger.info("%s: operacion auditada en %s (hash %s...).",
                       activo, TABLA_OPERACIONES, fila["hash_control"][:12])
        except RedFailSafeError as e:
            logger.critical("%s: fail-safe de red registrando auditoria: %s. Senal generada pero NO quedo registrada.",
                            activo, e)

        return senal

    def ejecutar_ciclo(self) -> List[Dict[str, Any]]:
        resultados = []
        for activo in self.pares:
            try:
                resultado = self.procesar_activo(activo)
            except Exception:
                logger.error("Excepcion no controlada procesando %s:\n%s", activo, traceback.format_exc())
                continue
            if resultado:
                resultado["activo"] = activo
                resultados.append(resultado)
        return resultados

    def ejecutar_bucle(self, intervalo_seg: int = 60) -> None:
        logger.info("TradingOrchestrator iniciado (activos=%s, intervalo=%ds, modo=simulacion).",
                    self.pares, intervalo_seg)
        while True:
            try:
                self.ejecutar_ciclo()
            except Exception:
                logger.critical("Ciclo abortado por excepcion no controlada:\n%s", traceback.format_exc())
            time.sleep(intervalo_seg)


def main():
    parser = argparse.ArgumentParser(
        description="TradingOrchestrator -- ciclo de senal + auditoria (modo simulacion, no coloca ordenes reales)"
    )
    parser.add_argument("--exchange", default="binance")
    parser.add_argument("--activos", default=",".join(PARES_DEFAULT))
    parser.add_argument("--intervalo", type=int, default=60)
    parser.add_argument("--capital-inicial", type=float, default=1000.0)
    parser.add_argument("--una-vez", action="store_true", help="Corre un solo ciclo y sale, en vez del bucle infinito")
    args = parser.parse_args()

    orquestador = TradingOrchestrator(
        exchange_id=args.exchange,
        pares=[p.strip() for p in args.activos.split(",") if p.strip()],
        capital_inicial=args.capital_inicial,
    )

    if args.una_vez:
        resultados = orquestador.ejecutar_ciclo()
        logger.info("Ciclo unico finalizado: %d activos procesados.", len(resultados))
        sys.exit(0)

    orquestador.ejecutar_bucle(intervalo_seg=args.intervalo)


if __name__ == "__main__":
    main()
