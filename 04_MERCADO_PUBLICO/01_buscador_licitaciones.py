#!/usr/bin/env python3
import argparse
import hashlib
import re
import sys
from datetime import datetime
from typing import List, Dict, Optional
import requests
from bs4 import BeautifulSoup
from core.db_manager import DatabaseManager
from core.resiliencia import red_segura

RSS_URL = "https://apis.mercadopublico.cl/rss/licitaciones"
USER_AGENT = "DepaFix-Buscador/1.0"
RE_FECHA_CIERRE = re.compile(r"Fecha de Cierre\s*[:]\s*(\d{2}-\d{2}-\d{4})", re.IGNORECASE)
RE_FECHA_PUBLICACION = re.compile(r"Fecha de Publicación\s*[:]\s*(\d{2}-\d{2}-\d{4})", re.IGNORECASE)

def extraer_codigo_licitacion(link: str) -> Optional[str]:
    match = re.search(r"id=(\d+)", link) or re.search(r"/(\d+)$", link)
    return match.group(1) if match else None

def parsear_fecha(fecha_str: str) -> Optional[str]:
    if not fecha_str: return None
    try: return datetime.strptime(fecha_str.strip(), "%d-%m-%Y").strftime("%Y-%m-%d")
    except ValueError: return None

def extraer_organismo(titulo: str, descripcion: str) -> str:
    match = re.search(r"^\(([^)]+)\)", titulo) or re.search(r"Organismo\s*[:]\s*([^\n]+)", descripcion, re.IGNORECASE)
    return match.group(1).strip() if match else "No especificado"

def obtener_licitaciones_desde_rss() -> List[Dict]:
    headers = {"User-Agent": USER_AGENT}
    resp = requests.get(RSS_URL, headers=headers, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.content, "xml")
    items = soup.find_all("item")
    licitaciones = []
    for item in items:
        titulo = item.title.string if item.title else ""
        link = item.link.string if item.link else ""
        descripcion = item.description.string if item.description else ""
        pub_date = item.pubDate.string if item.pubDate else ""
        codigo = extraer_codigo_licitacion(link)
        if not codigo: continue
        fecha_cierre_str = fecha_publicacion_str = None
        if descripcion:
            m = RE_FECHA_CIERRE.search(descripcion)
            if m: fecha_cierre_str = m.group(1)
            m = RE_FECHA_PUBLICACION.search(descripcion)
            if m: fecha_publicacion_str = m.group(1)
        if not fecha_publicacion_str and pub_date:
            try:
                dt_pub = datetime.strptime(pub_date, "%a, %d %b %Y %H:%M:%S %z")
                fecha_publicacion_str = dt_pub.strftime("%d-%m-%Y")
            except ValueError: pass
        fecha_pub = parsear_fecha(fecha_publicacion_str)
        fecha_cierre = parsear_fecha(fecha_cierre_str)
        estado = "Cerrada" if fecha_cierre and datetime.strptime(fecha_cierre, "%Y-%m-%d").date() < datetime.now().date() else "Publicada"
        organismo = extraer_organismo(titulo, descripcion)
        licitaciones.append({
            "codigo_licitacion": codigo,
            "titulo": titulo.strip(),
            "organismo": organismo,
            "fecha_publicacion": fecha_pub,
            "fecha_cierre": fecha_cierre,
            "estado": estado,
            "descripcion": descripcion.strip(),
            "palabras_clave": []
        })
    return licitaciones

def generar_idempotency_key(codigo: str) -> str:
    return hashlib.md5(codigo.encode()).hexdigest()

def guardar_licitaciones(licitaciones: List[Dict]) -> int:
    db = DatabaseManager().get_service_client()
    tabla = "licitaciones"
    nuevos = 0
    for lic in licitaciones:
        key = generar_idempotency_key(lic["codigo_licitacion"])
        existing = db.table(tabla).select("id").eq("idempotency_key", key).execute()
        if existing.data: continue
        data = {**lic, "idempotency_key": key}
        try:
            db.table(tabla).insert(data).execute()
            nuevos += 1
        except Exception as e:
            print(f"Error al insertar {lic['codigo_licitacion']}: {e}", file=sys.stderr)
    return nuevos

def buscar_licitaciones(palabras: str) -> List[Dict]:
    db = DatabaseManager().get_service_client()
    condiciones = []
    for palabra in palabras.split():
        condiciones.append(f"titulo ILIKE '%{palabra}%'")
        condiciones.append(f"descripcion ILIKE '%{palabra}%'")
    filtro = " OR ".join(condiciones)
    result = db.table("licitaciones").select("*").or_(filtro).limit(100).execute()
    return result.data

def verificar_estado():
    db = DatabaseManager().get_service_client()
    count = db.table("licitaciones").select("id", count="exact").execute()
    print(f"📊 Total licitaciones: {count.count}")
    ultimas = db.table("licitaciones").select("codigo_licitacion, titulo, fecha_publicacion").order("created_at", desc=True).limit(5).execute()
    print("📋 Últimas 5:")
    for reg in ultimas.data:
        print(f"  - {reg['codigo_licitacion']}: {reg['titulo'][:50]}... ({reg['fecha_publicacion']})")

def main():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--cron", action="store_true")
    group.add_argument("--buscar", type=str)
    group.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.check:
        verificar_estado()
    elif args.cron:
        print("🔍 Obteniendo licitaciones...")
        licitaciones = obtener_licitaciones_desde_rss()
        print(f"✅ {len(licitaciones)} licitaciones obtenidas.")
        if licitaciones:
            nuevos = guardar_licitaciones(licitaciones)
            print(f"📥 {nuevos} nuevas guardadas.")
    elif args.buscar:
        print(f"🔎 Buscando: '{args.buscar}'")
        resultados = buscar_licitaciones(args.buscar)
        print(f"📋 {len(resultados)} encontradas.")
        import json
        print(json.dumps(resultados, indent=2, ensure_ascii=False, default=str))

if __name__ == "__main__":
    main()
