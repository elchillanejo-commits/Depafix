#!/usr/bin/env python3
"""enviar_mail_sence.py — Envía mail SENCE con CSV de participantes y acta.pdf.

Requisitos .env: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY,
                 EVPREF_SMTP_USER, EVPREF_SMTP_PASSWORD (alias SMTP_USER/SMTP_PASSWORD)
                 EVPREF_SMTP_HOST (def. smtp.gmail.com), EVPREF_SMTP_PORT (def. 587)

Uso:
    python3 enviar_mail_sence.py --codigo_sence 1915171 --csv participantes.csv --acta acta.pdf --email destino@empresa.cl
    python3 enviar_mail_sence.py --codigo_sence 1915171 --csv participantes.csv --acta acta.pdf --email destino@empresa.cl --dry-run
"""
import argparse
import csv
import os
import smtplib
import sys
from email.message import EmailMessage
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def crear_supabase():
    url = (os.getenv("SUPABASE_URL") or "").strip()
    key = (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
    if not url or not key:
        raise SystemExit("Faltan SUPABASE_URL y SUPABASE_SERVICE_ROLE_KEY en .env")
    from supabase import create_client

    return create_client(url, key)


def obtener_curso(sb, codigo):
    resp = sb.table("cursos_sence").select("*").eq("codigo_sence", codigo).execute()
    if not resp.data:
        raise SystemExit(f"No existe curso con codigo_sence={codigo} en cursos_sence")
    return resp.data[0]


def leer_csv_participantes(ruta):
    with open(ruta, newline="", encoding="utf-8") as f:
        lector = csv.DictReader(f, delimiter=";")
        return [row for row in lector if any(str(v or "").strip() for v in row.values())]


def smtp_config():
    user = os.getenv("EVPREF_SMTP_USER") or os.getenv("SMTP_USER") or ""
    password = os.getenv("EVPREF_SMTP_PASSWORD") or os.getenv("SMTP_PASSWORD") or ""
    host = os.getenv("EVPREF_SMTP_HOST") or os.getenv("SMTP_HOST") or "smtp.gmail.com"
    port = int(os.getenv("EVPREF_SMTP_PORT") or os.getenv("SMTP_PORT") or "587")
    return user, password, host, port


def construir_asunto(curso):
    return f"Envío de Antecedentes – Curso {curso.get('nombre_curso', '')} – Código {curso.get('codigo_sence', '')}"


def construir_cuerpo(curso, participantes):
    lineas = "\n".join(
        f"- {p.get('nombre', p.get('Nombre', ''))} | {p.get('rut', p.get('Rut', p.get('RUT', '')))}"
        for p in participantes
    )
    return f"""Estimados señores SENCE:

Junto con saludar, se remiten los antecedentes del curso:

Nombre del Curso: {curso.get('nombre_curso', '')}
Código del Curso: {curso.get('codigo_sence', '')}
Modalidad: {curso.get('modalidad', '')}
Horas Cronológicas: {curso.get('horas_cronologicas', '')} horas
N° de Participantes: {curso.get('numero_participantes', len(participantes))}

Participantes adjuntos en CSV:
{lineas}

Documento adjunto: acta.pdf

Quedo atento a observaciones.

Saludos cordiales
"""


def enviar(curso, participantes, acta_path, destinatario):
    user, password, host, port = smtp_config()
    if not user or not password:
        raise SystemExit(
            "Faltan SMTP_USER / SMTP_PASSWORD (o EVPREF_SMTP_*) en .env. "
            "No se puede enviar sin credenciales SMTP."
        )

    msg = EmailMessage()
    msg["From"] = user
    msg["To"] = destinatario
    msg["Subject"] = construir_asunto(curso)
    msg.set_content(construir_cuerpo(curso, participantes))

    data_pdf = Path(acta_path).read_bytes()
    msg.add_attachment(
        data_pdf,
        maintype="application",
        subtype="pdf",
        filename=Path(acta_path).name,
    )

    with smtplib.SMTP(host, port, timeout=30) as server:
        server.starttls()
        server.login(user, password)
        server.send_message(msg)
    return True


def main():
    parser = argparse.ArgumentParser(description="Envía mail SENCE con CSV y acta.pdf")
    parser.add_argument("--codigo_sence", required=True, help="Código SENCE (ej: 1915171)")
    parser.add_argument("--csv", required=True, dest="csv", help="Ruta CSV participantes")
    parser.add_argument("--acta", required=True, help="Ruta acta.pdf")
    parser.add_argument("--email", required=True, dest="email", help="Email destino")
    parser.add_argument("--dry-run", action="store_true", help="Solo valida y muestra; no envía")
    args = parser.parse_args()

    ruta_csv = Path(args.csv).expanduser().resolve()
    ruta_acta = Path(args.acta).expanduser().resolve()
    if not ruta_csv.exists():
        raise SystemExit(f"No existe el CSV: {ruta_csv}")
    if not ruta_acta.exists():
        raise SystemExit(f"No existe el acta: {ruta_acta}")

    sb = crear_supabase()
    curso = obtener_curso(sb, args.codigo_sence)
    participantes = leer_csv_participantes(ruta_csv)

    print(f"Curso: {curso.get('codigo_sence')} - {curso.get('nombre_curso')}")
    print(f"Participantes en CSV: {len(participantes)}")
    print(f"Acta: {ruta_acta.name} ({ruta_acta.stat().st_size} bytes)")
    print(f"Destino: {args.email}")

    user, password, host, port = smtp_config()
    if not user or not password:
        print(
            "⚠️  SMTP_USER / SMTP_PASSWORD no configurados en .env (requeridos para envío real).",
            file=sys.stderr,
        )
        if not args.dry_run:
            raise SystemExit(1)
    else:
        print(f"SMTP: {host}:{port} usuario={user}")

    if args.dry_run:
        print("\n(dry-run: no se envió ningún mail)")
        print("\nAsunto:", construir_asunto(curso))
        print("\nCuerpo:\n", construir_cuerpo(curso, participantes)[:1500])
        return

    enviar(curso, participantes, ruta_acta, args.email)
    print(f"\n✅ Mail enviado a {args.email}")


if __name__ == "__main__":
    main()
