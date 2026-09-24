import os
import requests
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

async def notifier_telegram_worker(params: dict) -> dict:
    """Envía notificación a Telegram."""
    t0 = datetime.now(timezone.utc)
    
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    default_chat_id = os.getenv("TELEGRAM_CHAT_ID")
    
    if not token:
        return {"ok": False, "error": "Falta TELEGRAM_BOT_TOKEN"}
    
    mensaje = params.get("mensaje", "")
    nivel = params.get("nivel", "info")
    chat_id = params.get("chat_id") or default_chat_id
    
    if not chat_id:
        return {"ok": False, "error": "Falta chat_id y TELEGRAM_CHAT_ID"}
        
    # Prefijos según nivel
    iconos = {
        "info": "ℹ️",
        "warn": "⚠️",
        "error": "🔴"
    }
    icono = iconos.get(nivel, "ℹ️")
    
    texto_final = f"{icono} {mensaje}"
    
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": texto_final,
        "parse_mode": "Markdown"
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        
        duration_ms = int((datetime.now(timezone.utc) - t0).total_seconds() * 1000)
        
        return {
            "ok": True,
            "enviado": True,
            "chat_id": chat_id,
            "duracion_ms": duration_ms,
            "ejecutado": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        logger.error(f"Error enviando a Telegram: {e}")
        return {"ok": False, "error": str(e)}
