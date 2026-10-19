"""supabase_probe.py — Latencia + tamaño DB Supabase."""
from __future__ import annotations

import logging
import time
from typing import Any

from ceo.state import registrar_health

log = logging.getLogger(__name__)

TABLAS_CORE = ["velas_cripto", "operaciones_ejecutadas", "ceo_tasks"]
LATENCION_WARN_MS = 2000


def probe_supabase(client: Any) -> dict:
    """Mide latencia + cuenta filas de tablas core."""
    t0 = time.perf_counter()
    filas: dict[str, int | None] = {}
    err: str | None = None

    for tabla in TABLAS_CORE:
        try:
            r = client.table(tabla).select("id", count="exact").limit(1).execute()
            filas[tabla] = getattr(r, "count", None)
        except Exception as e:
            filas[tabla] = None
            err = str(e)[:150]

    latencia = int((time.perf_counter() - t0) * 1000)
    status = "ok"
    if err or latencia > LATENCION_WARN_MS:
        status = "warn" if err is None else "fail"

    payload = {"filas": filas, "error": err}
    registrar_health(client, "supabase", "core", status, latencia, payload)
    return {"status": status, "latencia_ms": latencia, "filas": filas}
