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

Arquitectura de despliegue (Railway): batch, no daemon. --una-vez corre un
ciclo completo (ingesta + señal + auditoria + reporte de salud) y termina
-- el "self-healing" y la cadencia periodica quedan a cargo de la
infraestructura (Cron Schedule del servicio + restartPolicyType=ON_FAILURE),
no de un loop de Python de larga vida. Un proceso que se reinicia limpio en
cada corrida no puede acumular fugas de memoria entre corridas; un daemon
infinito con time.sleep() sí puede. ejecutar_bucle() se mantiene solo para
uso local/manual (no es lo que corre en produccion, ver Dockerfile.worker).

Salud (Siegfried): cada ciclo (batch o dentro del bucle local) reporta a
salud_agentes vía core/salud_agentes.py -- 'HEALTHY' con métricas
(activos_analizados, señales_detectadas, memoria_uso_mb) al terminar, o
'CRITICAL' con el traceback si el ciclo aborta por una excepción no
controlada. En modo --una-vez, una excepción termina el proceso con exit
code != 0 después de reportar CRITICAL, para que Railway reinicie el
contenedor solo.

Uso:
    python3 src/trading/trading_orchestrator.py --una-vez  # modo produccion: un ciclo y sale
    python3 src/trading/trading_orchestrator.py --activos BTC/USDT,ETH/USDT --intervalo 60  # bucle local
"""
import argparse
import hashlib
import json
import logging
import resource
import signal
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

CORE_PATH = Path("/home/ibar/Proyectos/DepaFix/procurador")  # core/ vive en DepaFix/procurador/core (02_PROCURADOR fue renombrado ahi, commit 10462fe)
TRADE_ROOT = Path("/home/ibar/Proyectos/05_TRADE_CRIPTO")
for _p in (CORE_PATH, TRADE_ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from core.db_manager import DatabaseManager
from core.resiliencia import red_segura, RedFailSafeError
from core.salud_agentes import reportar_salud
from data_pipeline import PipelineVelas, PARES_DEFAULT
from crypto_trader_agent import TradingLogic
from report_generator import enviar_alerta, generar_reportes_vencidos

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

TABLA_OPERACIONES = "operaciones_ejecutadas"
NOMBRE_PROCESO = "trading_orchestrator"
DRAWDOWN_MAX_PCT = 2.0
VENTANA_VOLATILIDAD = 20


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
    """🧠 Trading Siegfried - Sistema de trading 24/7"""
    def __init__(self, exchange_id: str = "binance", pares: Optional[List[str]] = None,
                 capital_inicial: float = 1000.0):
        self.pares = pares or PARES_DEFAULT
        self.pipeline = PipelineVelas(exchange_id=exchange_id, pares=self.pares)
        self.signal_engine = SignalEngine()
        self.risk_manager = RiskManager(capital_inicial=capital_inicial)
        self._detener = False
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

        # Esquema real y vivo de operaciones_ejecutadas en Supabase: solo
        # symbol/price/side/ejecutada/hash_control (confirmado via schema de
        # PostgREST -- create_operaciones_ejecutadas.sql, que tenia
        # activo/temporalidad/precio_entrada/precio_salida/cantidad/motivo,
        # quedo desactualizado). temporalidad y motivo no tienen columna
        # donde ir hoy -- se pierden en la auditoria hasta que se agregue
        # una migracion; precio_salida/cantidad nunca se llenaban de todas
        # formas (siempre None, sin integracion de ordenes reales).
        fila = {
            "symbol": activo,
            "price": senal.get("precio_actual"),
            "side": senal.get("senal"),
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

        enviar_alerta(
            f"{activo} -> {senal.get('senal')} a {senal.get('precio_actual')} ({senal.get('motivo')}).",
            nivel="INFO",
        )
        return senal

    def _ingestar_velas_frescas(self) -> None:
        """Refresca velas_cripto desde el exchange antes de analizar. Sin
        esto, TradingLogic evaluaria sobre datos cada vez mas viejos --
        procesar_activo() solo LEE velas_cripto, nunca las actualiza (ver
        PipelineVelas.obtener_velas_para_analisis). PipelineVelas.ejecutar()
        ya es resiliente por combinacion par/temporalidad (nunca lanza, cada
        fallo se loguea y sigue con la siguiente); este try/except es
        defensa adicional para que un error inesperado acá tampoco frene el
        ciclo -- se analiza igual con las velas que ya haya en Supabase."""
        try:
            self.pipeline.ejecutar()
        except Exception:
            logger.error("Fallo inesperado ingiriendo velas frescas, se sigue con los datos existentes:\n%s",
                         traceback.format_exc())

    def ejecutar_ciclo(self) -> List[Dict[str, Any]]:
        self._ingestar_velas_frescas()
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

    def _uso_memoria_mb(self) -> float:
        """ru_maxrss es KB en Linux (donde corre el contenedor), no bytes --
        distinto a macOS. No hay ambigüedad real acá porque Dockerfile.worker
        siempre corre sobre python:3.12-slim (Linux)."""
        return round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1)

    def _ejecutar_ciclo_con_salud(self) -> List[Dict[str, Any]]:
        """Corre un ciclo completo y reporta el resultado a salud_agentes
        para que Siegfried sepa el estado sin entrar al servidor. Si el
        ciclo aborta por una excepción no controlada, reporta 'CRITICAL' con
        el traceback y vuelve a lanzar -- el llamador decide qué hacer (en
        modo --una-vez, main() sale con exit code != 0 para que Railway
        reinicie el contenedor; en el bucle local, ejecutar_bucle() lo
        atrapa y sigue en la siguiente iteración)."""
        try:
            resultados = self.ejecutar_ciclo()
        except Exception:
            detalle = traceback.format_exc()
            logger.critical("Ciclo abortado por excepcion no controlada:\n%s", detalle)
            reportar_salud(self._db, NOMBRE_PROCESO, "CRITICAL", detalle[-500:])
            enviar_alerta(f"trading_orchestrator: ciclo abortado por excepcion no controlada:\n{detalle[-500:]}",
                          nivel="CRITICAL")
            raise

        señales = sum(1 for r in resultados if r.get("senal") in ("COMPRA", "VENTA"))
        reportar_salud(
            self._db, NOMBRE_PROCESO, "HEALTHY",
            f"{len(resultados)} activo(s) analizado(s), {señales} señal(es) detectada(s).",
            metricas={
                "estado": "HEALTHY",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "activos_analizados": len(resultados),
                "señales_detectadas": señales,
                "memoria_uso_mb": self._uso_memoria_mb(),
            },
        )

        # Reportes periodicos: sin scheduler propio, se generan los que ya
        # vencieron en cada ciclo (ver docstring de generar_reportes_vencidos
        # en report_generator.py). Nunca lanza -- un fallo generando
        # reportes no debe afectar el resultado del ciclo de trading.
        try:
            generar_reportes_vencidos(self._db)
        except Exception:
            logger.error("Excepcion no controlada generando reportes periodicos:\n%s", traceback.format_exc())

        return resultados

    def _manejar_senal_apagado(self, signum, frame):
        logger.warning("Senal %s recibida: terminando el ciclo actual y deteniendose (sin matar a mitad de operacion).",
                       signal.Signals(signum).name)
        self._detener = True

    def ejecutar_bucle(self, intervalo_seg: int = 60) -> None:
        signal.signal(signal.SIGINT, self._manejar_senal_apagado)
        signal.signal(signal.SIGTERM, self._manejar_senal_apagado)
        logger.info("TradingOrchestrator iniciado (activos=%s, intervalo=%ds, modo=simulacion).",
                    self.pares, intervalo_seg)
        while not self._detener:
            try:
                self._ejecutar_ciclo_con_salud()
            except Exception:
                pass  # ya logueado y reportado a salud_agentes dentro de _ejecutar_ciclo_con_salud
            # Dormir en pasos de 1s (no time.sleep(intervalo_seg) de una)
            # para que una senal de apagado se note en <=1s en vez de tener
            # que esperar hasta 300s a que termine el sleep completo.
            for _ in range(intervalo_seg):
                if self._detener:
                    break
                time.sleep(1)
        logger.info("TradingOrchestrator detenido limpiamente.")


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
        try:
            resultados = orquestador._ejecutar_ciclo_con_salud()
        except Exception:
            # Ya quedo logueado y reportado como CRITICAL a salud_agentes en
            # _ejecutar_ciclo_con_salud. Salir con exit code != 0 es lo que
            # deja que Railway (restartPolicyType=ON_FAILURE) reinicie el
            # contenedor solo -- ver docstring del modulo.
            sys.exit(2)
        logger.info("Ciclo unico finalizado: %d activos procesados.", len(resultados))
        sys.exit(0)

    orquestador.ejecutar_bucle(intervalo_seg=args.intervalo)


if __name__ == "__main__":
    main()
