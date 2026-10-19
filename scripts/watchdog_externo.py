"""watchdog_externo.py — Corre en Vostro. Avisa si el CEO está caído."""
from __future__ import annotations

import logging
import os
import sys
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from supabase import create_client

load_dotenv()
log = logging.getLogger(__name__)

UMBRAL_MIN = 30


def check_watchdog() -> int:
    """Checks ceo_health frescura. Fail-open: retorna 0 siempre."""
    try:
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        if not url or not key:
            log.warning("watchdog: faltan credenciales")
            return 0

        client = create_client(url, key)
        resp = (client.table("ceo_health").select("ts")
                .order("ts", desc=True).limit(1).execute())
        rows = resp.data or []
        if not rows:
            log.warning("watchdog: ceo_health vacía")
            _notificar("🔴 CEO: ceo_health sin filas")
            return 0

        ultima = datetime.fromisoformat(rows[0]["ts"].replace("Z", "+00:00"))
        delta = (datetime.now(timezone.utc) - ultima).total_seconds() / 60

        if delta > UMBRAL_MIN:
            _notificar(f"🔴 CEO caído: última fila ceo_health hace {int(delta)} min")
        return 0
    except Exception as e:
        log.warning("watchdog falló: %s", e)
        return 0


def _notificar(msg: str) -> None:
    try:
        import requests
        token = os.environ.get("TELEGRAM_BOT_TOKEN")
        chat = os.environ.get("TELEGRAM_CHAT_ID")
        if not token or not chat:
            return
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat, "text": msg},
            timeout=10,
        )
    except Exception as e:
        log.warning("watchdog notif falló: %s", e)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    sys.exit(check_watchdog())
