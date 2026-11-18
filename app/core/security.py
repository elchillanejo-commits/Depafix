"""Seguridad ligera para los endpoints públicos de la API.

Sin dependencias nuevas: el rate limiter es en memoria y usa solo la stdlib,
para no alterar el pin de FastAPI/Starlette (ver BUG-005 en BUGS.md).
"""

import logging
import os
import secrets
import threading
import time
from collections import defaultdict, deque
from typing import Deque, Dict

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import APIKeyHeader

logger = logging.getLogger(__name__)

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

_warned_missing_key = False


async def verify_api_key(api_key: str | None = Depends(api_key_header)) -> None:
    """Exige X-API-Key solo cuando DEPAFIX_API_KEY está configurada.

    Si la variable no existe, deja pasar con un warning (modo desarrollo),
    para no romper el dashboard ni los endpoints ya operativos.
    """
    global _warned_missing_key

    expected = os.getenv("DEPAFIX_API_KEY")
    if not expected:
        if not _warned_missing_key:
            logger.warning(
                "DEPAFIX_API_KEY no configurada: endpoints públicos sin API Key "
                "(modo desarrollo). Configurarla en Railway para producción."
            )
            _warned_missing_key = True
        return

    if not api_key or not secrets.compare_digest(api_key, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-API-Key inválida o ausente.",
        )


class _InMemoryRateLimiter:
    """Ventana deslizante por cliente y ruta, thread-safe y sin Redis."""

    def __init__(self) -> None:
        self._hits: Dict[str, Deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    @staticmethod
    def _limits() -> tuple[int, int]:
        try:
            max_requests = int(os.getenv("RATE_LIMIT_REQUESTS", "100"))
        except ValueError:
            max_requests = 100
        try:
            window_seconds = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60"))
        except ValueError:
            window_seconds = 60
        return max(1, max_requests), max(1, window_seconds)

    def check(self, key: str) -> None:
        max_requests, window_seconds = self._limits()
        now = time.monotonic()

        with self._lock:
            bucket = self._hits[key]
            while bucket and bucket[0] <= now - window_seconds:
                bucket.popleft()

            if len(bucket) >= max_requests:
                retry_after = max(1, int(bucket[0] + window_seconds - now) + 1)
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=(
                        f"Límite de {max_requests} solicitudes por "
                        f"{window_seconds}s excedido."
                    ),
                    headers={"Retry-After": str(retry_after)},
                )

            bucket.append(now)


_limiter = _InMemoryRateLimiter()


async def enforce_rate_limit(request: Request) -> None:
    """Aplica el límite por IP + path (cada endpoint tiene su propio bucket)."""
    client_ip = request.client.host if request.client else "unknown"
    _limiter.check(f"{client_ip}:{request.url.path}")
