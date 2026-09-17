#!/usr/bin/env python3
import argparse
import os
import smtplib
import sys
import re
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Dict, Set
from core.db_manager import DatabaseManager

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM = os.getenv("SMTP_FROM", SMTP_USER)
EMAIL_SUBJECT_PREFIX = os.getenv("EMAIL_SUBJECT_PREFIX", "[DepaFix] Nueva Licitacion")

def obtener_licitaciones_nuevas(ultimas_horas: int = 24) -> List[Dict]:
    db = DatabaseManager().get_service_client()
    fecha_limite = datetime.now() - timedelta(hours=ultimas_horas)
    result = db.table("licitaciones").select("*").gte("created_at", fecha_limite.isoformat()).order("created_at", desc=True).execute()
    return result.data

def obtener_suscripciones_activas() -> List[Dict]:
    db = DatabaseManager().get_service_client()
    result = db.table("suscripciones").select("*").eq("activo", True).execute()
    return result.data

def filtrar_licitaciones_por_palabras(licitaciones: List[Dict], palabras: List[str]) -> List[Dict]:
    if not palabras:
        return licitaciones
    filtradas = []
    for lic in licitaciones:
        titulo = lic.get("titulo", "").lower()
        descripcion = lic.get("descripcion", "").lower()
        for palabra in palabras:
            if palabra.lower() in titulo or palabra.lower() in descripcion:
                filtradas.append(lic)
                break
    return filtradas

def obtener_alertas_previas(suscripcion_id: int, licitacion_ids: List[int]) -> Set[int]:
    db = DatabaseManager().get_service_client()
    result = db.table("alertas_enviadas").select("licitacion_id").eq("suscripcion_id", suscripcion_id).in_("licitacion_id", licitacion_ids).execute()
    return {row["licitacion_id"] for row in result.data}

def registrar_alertas(suscripcion_id: int, licitacion_ids: List[int]) -> int:
    db = DatabaseManager().get_service_client()
    registrados = 0
    for lic_id in licitacion_ids:
        try:
            db.table("alertas_enviadas").insert({"suscripcion_id": suscripcion_id, "licitacion_id": lic_id}).execute()
            registrados += 1
        except Exception as e:
            print(f"⚠️ Error al registrar alerta: {e}", file=sys.stderr)
    return registrados

def enviar_correo(destinatario: str, asunto: str, cuerpo_html: str) -> bool:
    if not SMTP_USER or not SMTP_PASSWORD:
        print("❌ SMTP no configurado.", file=sys.stderr)
        return False
    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = SMTP_FROM
        msg["To"] = destinatario
        msg["Subject"] = asunto
        cuerpo_texto = re.sub(r'<[^>]+>', '', cuerpo_html)
        cuerpo_texto = cuerpo_texto.replace("<br>", "\n").replace("</p>", "\n")
        msg.attach(MIMEText(cuerpo_texto, "plain"))
        msg.attach(MIMEText(cuerpo_html, "html"))
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
        return True
    except Exception as e:
        print(f"❌ Error enviando correo a {destinatario}: {e}", file=sys.stderr)
        return False

def generar_correo_licitaciones(licitaciones: List[Dict], suscripcion: Dict) -> str:
    nombre = suscripcion.get("cliente_nombre", "Cliente")
    palabras = ", ".join(suscripcion.get("palabras_clave", []))
    html = f"""<html><head><style>
body {{ font-family: Arial; }}
.licitacion {{ border:1px solid #ddd; padding:15px; margin:10px 0; border-radius:5px; }}
.titulo {{ font-size:16px; font-weight:bold; color:#2c3e50; }}
.organismo {{ color:#7f8c8d; font-size:14px; }}
.fecha {{ color:#95a5a6; font-size:12px; }}
</style></head><body>
<h2>📋 Nuevas licitaciones para {nombre}</h2>
<p><strong>Palabras clave:</strong> {palabras}</p>
<p><strong>Licitaciones encontradas:</strong> {len(licitaciones)}</p><hr>"""
    for lic in licitaciones:
        codigo = lic.get("codigo_licitacion", "N/A")
        titulo = lic.get("titulo", "Sin titulo")
        organismo = lic.get("organismo", "No especificado")
        fecha_pub = lic.get("fecha_publicacion", "Sin fecha")
        fecha_cierre = lic.get("fecha_cierre", "Sin fecha")
        descripcion = lic.get("descripcion", "")[:300]
        if len(lic.get("descripcion", "")) > 300:
            descripcion += "..."
        html += f"""<div class="licitacion"><div class="titulo">{titulo}</div>
<div class="organismo">🏛️ {organismo}</div>
<div class="fecha">📅 Publicacion: {fecha_pub} | 🏁 Cierre: {fecha_cierre}</div>
<div class="descripcion">{descripcion}</div>
<div class="enlace">🔗 <a href="https://www.mercadopublico.cl/Procurement/Modules/RFB/DetailsAcquisition.aspx?id={codigo}">Ver en ChileCompra</a></div></div>"""
    html += """<hr><p style="color:#95a5a6;font-size:12px;">Correo automatico de DepaFix.</p></body></html>"""
    return html

def procesar_alertas(dry_run: bool = False, ultimas_horas: int = 24) -> int:
    licitaciones = obtener_licitaciones_nuevas(ultimas_horas)
    if not licitaciones:
        print("ℹ️ No hay licitaciones nuevas.")
        return 0
    print(f"📊 {len(licitaciones)} licitaciones nuevas.")
    suscripciones = obtener_suscripciones_activas()
    if not suscripciones:
        print("ℹ️ No hay suscripciones activas.")
        return 0
    print(f"👥 {len(suscripciones)} suscripciones activas.")
    total_alertas = 0
    for suscripcion in suscripciones:
        susc_id = suscripcion["id"]
        email = suscripcion["cliente_email"]
        palabras = suscripcion.get("palabras_clave", [])
        lic_filtradas = filtrar_licitaciones_por_palabras(licitaciones, palabras)
        if not lic_filtradas:
            continue
        lic_ids = [l["id"] for l in lic_filtradas]
        ya_enviadas = obtener_alertas_previas(susc_id, lic_ids)
        lic_nuevas = [l for l in lic_filtradas if l["id"] not in ya_enviadas]
        if not lic_nuevas:
            continue
        if dry_run:
            print(f"[DRY RUN] {email}: {len(lic_nuevas)} licitaciones nuevas")
            for lic in lic_nuevas:
                print(f"    - {lic['titulo']}")
            continue
        asunto = f"{EMAIL_SUBJECT_PREFIX} - {len(lic_nuevas)} oportunidades"
        cuerpo_html = generar_correo_licitaciones(lic_nuevas, suscripcion)
        if enviar_correo(email, asunto, cuerpo_html):
            registrados = registrar_alertas(susc_id, [l["id"] for l in lic_nuevas])
            total_alertas += registrados
            print(f"✅ Alertas enviadas a {email}: {len(lic_nuevas)} licitaciones")
        else:
            print(f"❌ Error al enviar a {email}")
    return total_alertas

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ultimas-horas", type=int, default=24)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    print("🚀 Iniciando sistema de alertas...")
    total = procesar_alertas(dry_run=args.dry_run, ultimas_horas=args.ultimas_horas)
    print(f"✅ Procesado: {total} alertas enviadas.")

if __name__ == "__main__":
    main()
