"""health_probe.py — Worker que ejecuta sensores y escribe ceo_health."""
from __future__ import annotations

import logging

from ceo.sensors.run_all import run_all

log = logging.getLogger(__name__)


def health_probe_worker(params: dict | None = None) -> dict:
    """Ejecuta todos los sensores. Fail-open."""
    try:
        return {"ok": True, "resultados": run_all()}
    except Exception as e:
        log.exception("health_probe falló")
        return {"ok": False, "error": str(e)[:200]}
