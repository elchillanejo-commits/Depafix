"""notifier.py — Telegram notifier con fail-open."""
from __future__ import annotations

import logging
import os

import requests

log = logging.getLogger(__name__)

TIMEOUT_S = 10
API = "https://api.telegram.org"


def notificar_telegram(mensaje: str, nivel: str = "info") -> bool:
    """Envía mensaje a Telegram. Fail-open: nunca lanza."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        log.warning("faltan TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_ID")
        return False

    prefijo = {"info": "ℹ️", "warn": "⚠️", "fail": "🔴"}.get(nivel, "ℹ️")
    texto = f"{prefijo} {mensaje}"
    try:
        r = requests.post(
            f"{API}/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": texto[:4000]},
            timeout=TIMEOUT_S,
        )
        return r.status_code == 200
    except Exception as e:
        log.warning("notificar_telegram falló: %s", e)
        return False
