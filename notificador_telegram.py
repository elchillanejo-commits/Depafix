#!/usr/bin/env python3
"""
notificador_telegram.py — Envía los resultados del radar a Telegram.
Lee las credenciales desde el archivo .env o desde las variables de entorno.
"""
import os
import sys
import requests
from pathlib import Path
from dotenv import load_dotenv

# Cargar variables desde el archivo .env (si existe)
load_dotenv()

# Acepta ambos nombres de variable por compatibilidad
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Validación de credenciales
if not TOKEN or not CHAT_ID:
    print("[ERROR] Faltan TELEGRAM_BOT_TOKEN (o TELEGRAM_TOKEN) o TELEGRAM_CHAT_ID en el .env o entorno.", file=sys.stderr)
    sys.exit(1)

LOGS_DIR = Path("logs/analisis_web")

# Palabras que indican bloqueo o error en el contenido extraído
PALABRAS_BLOQUEO = ["access denied", "403 forbidden", "captcha", "cloudflare", "attention required"]


def enviar_mensaje(texto: str) -> bool:
    """Envía un mensaje a Telegram. Trunca si supera el límite de 4096 caracteres."""
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    max_len = 4000
    if len(texto) > max_len:
        texto = texto[:max_len] + "\n\n[... truncado por longitud ...]"
    
    payload = {"chat_id": CHAT_ID, "text": texto}
    try:
        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        return True
    except Exception as e:
        print(f"[ERROR] Fallo al enviar a Telegram: {e}", file=sys.stderr)
        return False


def main() -> int:
    if not LOGS_DIR.exists():
        enviar_mensaje("⚠️ No se encontró el directorio de logs. ¿Falló el radar?")
        print("[ERROR] Directorio de logs no encontrado.", file=sys.stderr)
        return 1

    archivos = sorted(LOGS_DIR.glob("*.txt"))
    if not archivos:
        enviar_mensaje("⚠️ El radar terminó, pero no se generaron archivos de análisis.")
        return 0

    msg = "✅ *Reporte Radar PYMES*\n\n"
    archivos_validos = 0

    for arch in archivos:
        try:
            contenido = arch.read_text(encoding="utf-8").strip()
            
            # Validar si el contenido es muy corto o contiene palabras de bloqueo
            if len(contenido) < 500 or any(p in contenido.lower() for p in PALABRAS_BLOQUEO):
                msg += f"⚠️ *{arch.name}*: Bloqueado o vacío (<500 chars). No se envía contenido.\n\n"
                continue
            
            archivos_validos += 1
            preview = contenido[:300].replace("*", "").replace("_", "") + "..."
            msg += f"📄 *{arch.name}*\n{preview}\n\n"
            
        except Exception as e:
            msg += f"❌ Error leyendo {arch.name}: {e}\n\n"

    if archivos_validos == 0:
        msg += "🚨 *ALERTA:* Ningún archivo pasó la validación de contenido.\n"

    if enviar_mensaje(msg):
        print(f"[OK] Notificación enviada. Archivos válidos: {archivos_validos}/{len(archivos)}")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
