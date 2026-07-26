"""
resiliencia.py -- decorador de reintentos para llamadas de red (Supabase,
exchanges, APIs externas, Claude), compartido por los agentes del repo para
no reimplementar la misma politica de reintentos en cada uno.

Cada intento esta acotado a `latencia_max` segundos: si lo excede o lanza
excepcion, reintenta durmiendo 1s * numero_de_intento entre cada uno, hasta
`max_reintentos` veces. Agotados los reintentos, levanta RedFailSafeError --
fail-safe explicito en vez de dejar que el error de red se propague crudo o
que el llamador se quede reintentando indefinidamente. El llamador decide
que hacer ante ese fail-safe (caer a un mock, usar un valor de respaldo,
abortar el ciclo), nunca debe reintentar por su cuenta por fuera de este
decorador.
"""
import functools
import logging
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from typing import Callable

logger = logging.getLogger(__name__)

MAX_REINTENTOS = 2
LATENCIA_MAX_SEG = 5.0
OPERACION_DEFAULT = "operación"

# Pool compartido por todos los agentes que importen este modulo: las
# llamadas de red que envuelve (httpx via supabase-py, ccxt, anthropic) son
# sincronicas y no se pueden cancelar de forma preventiva a mitad de un
# socket. Usar .result(timeout=) deja de esperar y trata el intento como
# fallido -- que es la semantica util aca ("no bloquees el ciclo mas de
# latencia_max"), aunque el hilo de fondo pueda seguir corriendo hasta que
# la llamada subyacente resuelva sola.
_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="red-resiliente")


class RedFailSafeError(RuntimeError):
    """Senal de desconexion segura: se agotaron los reintentos o se excedio
    la latencia maxima. El llamador debe tratarlo como "esta llamada no
    resulto", nunca reintentar por su cuenta por fuera del decorador."""


def _con_latencia_maxima(func: Callable, segundos: float, operacion: str) -> Callable:
    @functools.wraps(func)
    def envoltura(*args, **kwargs):
        futuro = _executor.submit(func, *args, **kwargs)
        try:
            return futuro.result(timeout=segundos)
        except FutureTimeoutError:
            raise RedFailSafeError(
                f"{operacion}: excedio latencia maxima de {segundos * 1000:.0f}ms"
            ) from None
    return envoltura


def red_segura(max_reintentos: int = MAX_REINTENTOS, latencia_max: float = LATENCIA_MAX_SEG,
               operacion: str = OPERACION_DEFAULT) -> Callable:
    """Decorador para toda llamada de red: reintenta hasta max_reintentos
    veces, durmiendo 1s * numero_de_intento entre cada reintento, antes de
    levantar RedFailSafeError.

    `operacion` es una etiqueta legible para los logs y el mensaje de error
    (ej. "resumir con Claude"), independiente del nombre tecnico de la
    funcion decorada.
    """
    def decorador(func: Callable) -> Callable:
        func_acotado = _con_latencia_maxima(func, latencia_max, operacion)

        @functools.wraps(func)
        def envoltura(*args, **kwargs):
            ultimo_error = None
            for intento in range(1, max_reintentos + 1):
                try:
                    return func_acotado(*args, **kwargs)
                except Exception as e:
                    ultimo_error = e
                    if intento < max_reintentos:
                        espera = 1.0 * intento
                        logger.warning(
                            "%s: fallo (intento %d/%d): %s. Reintentando en %.1fs.",
                            operacion, intento, max_reintentos, e, espera,
                        )
                        time.sleep(espera)
                    else:
                        logger.warning(
                            "%s: fallo (intento %d/%d): %s.",
                            operacion, intento, max_reintentos, e,
                        )
            logger.critical(
                "%s: agotados %d reintentos, desconexion segura (fail-safe).",
                operacion, max_reintentos,
            )
            raise RedFailSafeError(f"{operacion}: agoto {max_reintentos} reintentos") from ultimo_error
        return envoltura
    return decorador
