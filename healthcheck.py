#!/usr/bin/env python3
"""Verifica que el log del radar de PYMES de las 03:00 se haya creado.

Si el log no existe, no contiene la palabra FIN o no contiene "estado 0",
envía una alerta por Telegram usando TELEGRAM_TOKEN y TELEGRAM_CHAT_ID
del entorno o .env.
"""

import argparse
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
LOG_DIR = BASE_DIR / "logs"
ARCHIVO_ENV = BASE_DIR / ".env"
HORA_ESPERADA = 3
PATRON_LOG = "trabajo_nocturno_{fecha}_*.log"
TIMEOUT_TELEGRAM = 20


def cargar_env():
    """Carga .env dando prioridad a sus valores sobre el entorno.

    El entorno puede tener placeholders (p. ej. TELEGRAM_BOT_TOKEN=tu_token...),
    por eso el .env debe sobrescribirlos.
    """
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
        os.environ[clave] = valor


def fecha_objetivo(ahora):
    """Devuelve el día cuyo turno de las 03:00 debe revisarse."""
    if ahora.hour < HORA_ESPERADA:
        return (ahora - timedelta(days=1)).date()
    return ahora.date()


def buscar_log(fecha):
    """Busca el log del turno de las 03:00 para la fecha indicada."""
    patron = PATRON_LOG.format(fecha=fecha.isoformat())
    candidatos = sorted(LOG_DIR.glob(patron))
    if not candidatos:
        return None
    return max(candidatos, key=lambda ruta: ruta.stat().st_mtime)


def evaluar_log(ruta):
    """Devuelve un motivo de fallo o None si el log está correcto."""
    try:
        contenido = ruta.read_text(encoding="utf-8", errors="replace")
    except OSError as error:
        return f"no se pudo leer el log ({error})"

    if not contenido.strip():
        return "el log está vacío"

    if re.search(r"\bFIN\b", contenido) is None:
        return "no se encontró la palabra FIN (ejecución incompleta o interrumpida)"

    if re.search(r"\bestado\s+0\b", contenido) is None:
        return "no se encontró 'estado 0' en el log"

    return None


def enviar_alerta_telegram(mensaje):
    token = (
        os.environ.get("TELEGRAM_TOKEN", "").strip()
        or os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    )
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        raise RuntimeError(
            "faltan TELEGRAM_TOKEN (o TELEGRAM_BOT_TOKEN) y TELEGRAM_CHAT_ID "
            "en el entorno o en .env"
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
            f"no se pudo enviar la alerta a Telegram ({type(error).__name__})"
        ) from None

    if not cuerpo.get("ok"):
        raise RuntimeError("Telegram no confirmó el envío de la alerta")


def construir_mensaje(fecha, motivo):
    return (
        "ALERTA Radar PYMES\n"
        f"El log de las {HORA_ESPERADA:02d}:00 del {fecha.isoformat()} falló: {motivo}.\n"
        f"Se esperaba: {LOG_DIR / PATRON_LOG.format(fecha=fecha.isoformat())}"
    )


def main():
    parser = argparse.ArgumentParser(
        description="Verifica el log nocturno del radar de PYMES y alerta por Telegram."
    )
    parser.add_argument(
        "--fecha",
        type=date.fromisoformat,
        default=None,
        help="Fecha a revisar en formato YYYY-MM-DD (por defecto, el último turno de 03:00).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Muestra el resultado sin enviar nada a Telegram.",
    )
    parser.add_argument(
        "--test",
        "--probar",
        dest="test",
        action="store_true",
        help="Envía un mensaje de prueba a Telegram y termina.",
    )
    args = parser.parse_args()

    cargar_env()

    if args.test:
        mensaje = (
            "PRUEBA Healthcheck Radar PYMES\n"
            "La conexión con Telegram funciona correctamente."
        )
        if args.dry_run:
            print("DRY-RUN: no se envía mensaje de prueba.")
            print(mensaje)
            return 0
        try:
            enviar_alerta_telegram(mensaje)
        except RuntimeError as error:
            print(f"ERROR: {error}", file=sys.stderr)
            return 1
        print("Mensaje de prueba enviado por Telegram.")
        return 0

    fecha = args.fecha or fecha_objetivo(datetime.now())
    ruta_log = buscar_log(fecha)

    if ruta_log is None:
        motivo = "no se encontró el log (el proceso de las 03:00 no se ejecutó)"
    else:
        motivo = evaluar_log(ruta_log)

    if motivo is None:
        print(f"OK: {ruta_log.name} existe y la ejecución fue correcta.")
        return 0

    mensaje = construir_mensaje(fecha, motivo)
    if args.dry_run:
        print("DRY-RUN: no se envía alerta.")
        print(mensaje)
        return 0

    try:
        enviar_alerta_telegram(mensaje)
    except RuntimeError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print("Alerta de healthcheck enviada por Telegram.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
