#!/usr/bin/env python3
"""Alerta por Telegram si el log del trabajo nocturno lleva 24 horas sin cambios."""

import json
import os
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
ARCHIVO_ENV = BASE_DIR / ".env"
LOG_DIR = BASE_DIR / "logs"
PATRON_LOG = "modo_nocturno_*.log"
MAXIMO_SEGUNDOS_SIN_CAMBIOS = 24 * 60 * 60
TIMEOUT_TELEGRAM = 20


def cargar_env():
    """Carga variables de .env sin sobrescribir las variables del entorno."""
    if not ARCHIVO_ENV.is_file():
        return

    for linea in ARCHIVO_ENV.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        clave, valor = linea.split("=", 1)
        clave = clave.strip()
        if clave.startswith("export "):
            clave = clave.removeprefix("export ").strip()
        valor = valor.strip()
        if len(valor) >= 2 and valor[0] == valor[-1] and valor[0] in {'"', "'"}:
            valor = valor[1:-1]
        os.environ.setdefault(clave, valor)


def obtener_ultimo_log():
    """Devuelve el log nocturno modificado más recientemente, si existe."""
    logs = (ruta for ruta in LOG_DIR.glob(PATRON_LOG) if ruta.is_file())
    return max(logs, key=lambda ruta: ruta.stat().st_mtime, default=None)


def enviar_alerta_telegram(mensaje):
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        raise RuntimeError(
            "Configura TELEGRAM_BOT_TOKEN y TELEGRAM_CHAT_ID en el entorno o en .env."
        )

    datos = urllib.parse.urlencode({"chat_id": chat_id, "text": mensaje}).encode()
    solicitud = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=datos,
        method="POST",
    )
    try:
        with urllib.request.urlopen(solicitud, timeout=TIMEOUT_TELEGRAM) as respuesta:
            cuerpo = json.loads(respuesta.read().decode("utf-8"))
    except Exception as error:
        raise RuntimeError(
            f"No se pudo enviar la alerta a Telegram ({type(error).__name__})."
        ) from None

    if not cuerpo.get("ok"):
        raise RuntimeError("Telegram no confirmó el envío de la alerta.")


def main():
    cargar_env()
    ultimo_log = obtener_ultimo_log()

    if ultimo_log is None:
        mensaje = (
            "ALERTA Radar de PYMES\n"
            f"No se encontró ningún {PATRON_LOG} en {LOG_DIR}. "
            "El proceso de las 03:00 podría no haberse ejecutado."
        )
    else:
        ultima_modificacion = ultimo_log.stat().st_mtime
        antiguedad = max(0, time.time() - ultima_modificacion)
        if antiguedad < MAXIMO_SEGUNDOS_SIN_CAMBIOS:
            print(
                f"OK: {ultimo_log.name} se modificó hace "
                f"{antiguedad / 3600:.1f} horas."
            )
            return 0

        fecha_utc = datetime.fromtimestamp(
            ultima_modificacion, tz=timezone.utc
        ).strftime("%Y-%m-%d %H:%M:%S UTC")
        mensaje = (
            "ALERTA Radar de PYMES\n"
            "El log del proceso de las 03:00 no se modifica desde hace "
            f"{antiguedad / 3600:.1f} horas.\n"
            f"Archivo: {ultimo_log}\n"
            f"Última modificación: {fecha_utc}"
        )

    try:
        enviar_alerta_telegram(mensaje)
    except RuntimeError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print("Alerta de healthcheck enviada por Telegram.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
