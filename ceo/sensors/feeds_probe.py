"""feeds_probe.py — Chequea /health del CEO service.

Usa dominio interno de Railway si está disponible para evitar
el falso timeout de auto-referencia (worker chequeando su propio contenedor).
"""
from __future__ import annotations

import logging
import os
import time

import requests

from ceo.state import registrar_health

log = logging.getLogger(__name__)

# Preferir dominio interno si Railway lo expone (evita auto-timeout)
INTERNO = os.environ.get("RAILWAY_PRIVATE_DOMAIN")
CEO_URL_INTERNA = f"http://{INTERNO}" if INTERNO else None
CEO_URL_PUBLICA = os.environ.get(
    "CEO_URL", "https://depafix-ceo-production.up.railway.app"
)
TIMEOUT_S = 20  # Aumentado de 10 a 20


def _urls_a_probar() -> list[str]:
    urls = []
    if CEO_URL_INTERNA:
        urls.append(CEO_URL_INTERNA)
    urls.append(CEO_URL_PUBLICA)
    return urls


def probe_feeds(client) -> dict:
    """Chequea /health. Fail-open.

    Si corre DENTRO de Railway (RAILWAY_ENVIRONMENT_ID presente),
    retorna status=skip. Chequearse a sí mismo desde el propio
    contenedor causa timeouts porque el event loop está ocupado.
    """
    import os
    if os.environ.get("RAILWAY_ENVIRONMENT_ID"):
        from ceo.state import registrar_health
        registrar_health(
            client, "feed", "depafix-ceo", "skip", None,
            {"razon": "auto_referencia_deshabilitada"},
        )
        return {"status": "skip", "razon": "auto_referencia"}

    return _probe_feeds_interno(client)


def _probe_feeds_interno(client) -> dict:
    ultimo_error = None
    for base in _urls_a_probar():
        url = f"{base}/health"
        t0 = time.perf_counter()
        try:
            r = requests.get(url, timeout=TIMEOUT_S)
            latencia = int((time.perf_counter() - t0) * 1000)
            status = "ok" if r.status_code == 200 else "fail"
            payload = {
                "health_code": r.status_code,
                "url": base,
                "via": "interno" if base == CEO_URL_INTERNA else "publico",
            }
            registrar_health(client, "feed", "depafix-ceo", status, latencia, payload)
            return {"status": status, "latencia_ms": latencia, **payload}
        except Exception as e:
            ultimo_error = str(e)[:150]
            continue

    # Todas las URLs fallaron
    registrar_health(
        client, "feed", "depafix-ceo", "fail", None,
        {"error": ultimo_error, "urls_probadas": _urls_a_probar()},
    )
    return {"status": "fail", "error": ultimo_error}
