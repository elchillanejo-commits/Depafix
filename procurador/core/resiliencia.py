"""
resiliencia.py -- decorador de reintentos con backoff exponencial para
llamadas de red (Supabase, exchanges, APIs externas), compartido por todos
los agentes del repo (src/trading/trading_orchestrator.py, core/trade_agent.py,
etc.) para no reimplementar la misma politica de reintentos en cada uno.

Cada intento esta acotado a `latencia_max` segundos: si lo excede o lanza
excepcion, reintenta con backoff exponencial + jitter hasta `max_reintentos`
veces. Agotados los reintentos, levanta RedFailSafeError -- fail-safe
explicito en vez de dejar que el error de red se propague crudo o que el
llamador se quede reintentando indefinidamente. El llamador decide que hacer
ante ese fail-safe (caer a cache, usar un valor de respaldo, abortar el
ciclo), nunca debe reintentar por su cuenta por fuera de este decorador.
"""
import functools
import logging
import random
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from typing import Callable

logger = logging.getLogger(__name__)

MAX_LATENCIA_SEG = 0.5
MAX_REINTENTOS = 5
BACKOFF_BASE_SEG = 2

# Pool compartido por todos los agentes que importen este modulo: las
# llamadas de red que envuelve (httpx via supabase-py, ccxt) son sincronicas
# y no se pueden cancelar de forma preventiva a mitad de un socket. Usar
# .result(timeout=) deja de esperar y trata el intento como fallido -- que es
# la semantica util aca ("no bloquees el ciclo mas de latencia_max"), aunque
# el hilo de fondo pueda seguir corriendo hasta que la llamada subyacente
# resuelva sola.
_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="red-resiliente")


class RedFailSafeError(RuntimeError):
    """Senal de desconexion segura: se agotaron los reintentos o se excedio
    la latencia maxima. El llamador debe tratarlo como "esta llamada no
    resulto", nunca reintentar por su cuenta por fuera del decorador."""


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
    """Decorador para toda llamada de red: reintenta con backoff exponencial
    + jitter hasta max_reintentos veces antes de levantar RedFailSafeError."""
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
