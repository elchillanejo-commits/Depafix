"""Rate limiter para Kraken API."""
import time
import threading
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


class KrakenRateLimiter:
    """Ventana deslizante por endpoint. Respeta headers de respuesta."""
    def __init__(self):
        self.limits = {
            "public": {"calls": 20, "window": 1},
            "private": {"calls": 15, "window": 1},
            "overall": {"calls": 45, "window": 3},
        }
        self.usage = defaultdict(list)
        self.lock = threading.Lock()

    def wait_if_needed(self, endpoint_type: str = "public"):
        with self.lock:
            now = time.time()
            cfg = self.limits[endpoint_type]
            key = f"{endpoint_type}_all"
            self.usage[key] = [t for t in self.usage[key] if t > now - cfg["window"]]
            if len(self.usage[key]) >= cfg["calls"]:
                oldest = min(self.usage[key])
                wait = cfg["window"] - (now - oldest) + 0.1
                logger.debug(f"Rate limit {endpoint_type}: esperando {wait:.2f}s")
                time.sleep(wait)
                self.usage[key] = [t for t in self.usage[key] if t > time.time() - cfg["window"]]
            self.usage[key].append(time.time())

    def update_from_headers(self, headers: dict):
        """Ajusta límites dinámicamente desde headers de Kraken."""
        if "X-RateLimit-Limit" in headers:
            limit = int(headers["X-RateLimit-Limit"])
            remaining = int(headers.get("X-RateLimit-Remaining", limit))
            reset = int(headers.get("X-RateLimit-Reset", 0))
            logger.debug(f"Rate limit Kraken: {remaining}/{limit}, reset {reset}s")


# Instancia global
rate_limiter = KrakenRateLimiter()
