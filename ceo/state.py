"""state.py — Escritura de métricas de salud a ceo_health."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from dotenv import load_dotenv

load_dotenv()
log = logging.getLogger(__name__)


def registrar_health(
    client: Any,
    source: str,
    target: str,
    status: str,
    latency_ms: int | None = None,
    payload: dict | None = None,
) -> bool:
    """Inserta fila en ceo_health. Fail-open."""
    if status not in ("ok", "warn", "fail", "skip"):
        log.warning("status inválido: %s", status)
        return False
    try:
        client.table("ceo_health").insert({
            "ts": datetime.now(timezone.utc).isoformat(),
            "source": source,
            "target": target,
            "status": status,
            "latency_ms": latency_ms,
            "payload": payload or {},
        }).execute()
        return True
    except Exception as e:
        log.warning("registrar_health falló: %s", e)
        return False


def leer_ultimo(client: Any, source: str, target: str) -> dict | None:
    """Lee última fila para (source, target). Fail-open → None."""
    try:
        resp = (
            client.table("ceo_health")
            .select("*")
            .eq("source", source)
            .eq("target", target)
            .order("ts", desc=True)
            .limit(1)
            .execute()
        )
        rows = resp.data or []
        return rows[0] if rows else None
    except Exception as e:
        log.warning("leer_ultimo falló: %s", e)
        return None
