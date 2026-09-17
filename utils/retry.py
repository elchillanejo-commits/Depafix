"""Decorador de reintentos con exponential backoff."""
import time
import functools
import logging
from typing import Callable, Any, Optional

logger = logging.getLogger(__name__)


def retry(
    max_retries: int = 5,
    base_delay: float = 1.0,
    backoff_factor: float = 2.0,
    exceptions: tuple = (Exception,),
    on_retry: Optional[Callable] = None,
):
    """Decorador para reintentar una función con backoff exponencial."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            _delay = base_delay
            for attempt in range(1, max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    if attempt == max_retries:
                        logger.error(f"Fallo después de {max_retries} reintentos: {e}")
                        raise
                    logger.warning(
                        f"Intento {attempt}/{max_retries} falló en {func.__name__}: {e}. "
                        f"Reintentando en {_delay:.2f}s"
                    )
                    if on_retry:
                        on_retry(attempt, e)
                    time.sleep(_delay)
                    _delay *= backoff_factor
            return None
        return wrapper
    return decorator
