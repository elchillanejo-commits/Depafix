"""Manejo de señales para apagado controlado."""
import signal
import logging
from threading import Event

logger = logging.getLogger(__name__)


class GracefulShutdown:
    def __init__(self):
        self._event = Event()
        self._setup()

    def _setup(self):
        signal.signal(signal.SIGINT, self._handler)
        signal.signal(signal.SIGTERM, self._handler)
        logger.info("Graceful shutdown activo (Ctrl+C para detener).")

    def _handler(self, sig, frame):
        logger.info(f"Señal {sig} recibida. Apagando...")
        self._event.set()

    def is_shutting_down(self) -> bool:
        return self._event.is_set()

    def wait(self, timeout: float = None):
        self._event.wait(timeout=timeout)


shutdown = GracefulShutdown()
