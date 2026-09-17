#!/usr/bin/env python3
"""
Scraper de licitaciones de la Región Metropolitana.
Usa la misma API real de Mercado Público que 02_actualizar_licitaciones.py.

La región NO viene en el listado por fecha (Listado[] solo trae
CodigoExterno/Nombre/CodigoEstado/FechaCierre) -- solo aparece en el detalle
por código (Comprador.RegionUnidad). Por eso el flujo es: listar candidatos
por fecha, pedir el detalle de cada uno (acotado por --limite para no hacer
cientos de requests) y filtrar por región ahí.
"""

import os
import sys
import time
import hashlib
import argparse
import requests
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from core.db_manager import DatabaseManager
from core.resiliencia import red_segura

load_dotenv(BASE_DIR / ".env")

API_BASE = "https://api.mercadopublico.cl/servicios/v1/publico/licitaciones.json"
TICKET = os.getenv("MERCADO_PUBLICO_API_KEY")

# Pausa entre requests para evitar "Hemos detectado peticiones simultáneas" (Codigo 10500)
PAUSA_ENTRE_REQUESTS = 2.5

# Los nombres oficiales de región traen variantes ("Región Metropolitana de
# Santiago") y a veces espacios sobrantes -- basta con esta subcadena.
REGION_RM = "metropolitana"


@red_segura(max_reintentos=3, latencia_max=15.0, operacion="Mercado Público: listar por fecha")
def _listar_por_fecha(fecha_ddmmaaaa: str, estado: str) -> Dict:
    resp = requests.get(API_BASE, params={"ticket": TICKET, "fecha": fecha_ddmmaaaa, "estado": estado}, timeout=30)
    resp.raise_for_status()
    return resp.json()


@red_segura(max_reintentos=3, latencia_max=15.0, operacion="Mercado Público: detalle por codigo")
def _detalle_licitacion(codigo: str) -> Dict:
    resp = requests.get(API_BASE, params={"ticket": TICKET, "codigo": codigo}, timeout=30)
    resp.raise_for_status()
    return resp.json()


def obtener_codigos_candidatos(dias_atras: int, limite: int) -> List[str]:
    """Lista códigos publicados en los últimos `dias_atras` días, hasta `limite`."""
    if not TICKET:
        print("❌ Falta MERCADO_PUBLICO_API_KEY en .env", file=sys.stderr)
        return []

    codigos_vistos = []
    vistos_set = set()
    for dias in range(dias_atras):
        fecha = (datetime.now() - timedelta(days=dias)).strftime("%d%m%Y")
        try:
            print(f"📅 Consultando {fecha}...")
            data = _listar_por_fecha(fecha, estado="publicada")
        except Exception as e:
            print(f"❌ Error consultando fecha={fecha}: {e}", file=sys.stderr)
            continue

        lista = data.get("Listado", []) or []
        print(f"   {len(lista)} licitaciones publicadas ese día")
        for item in lista:
            codigo = item.get("CodigoExterno")
            if codigo and codigo not in vistos_set:
                vistos_set.add(codigo)
                codigos_vistos.append(codigo)
            if len(codigos_vistos) >= limite:
                break

        time.sleep(PAUSA_ENTRE_REQUESTS)
        if len(codigos_vistos) >= limite:
            break

    return codigos_vistos[:limite]


def extraer_campos_licitacion(item: Dict) -> Dict:
    """Extrae los campos relevantes del detalle (por `codigo`) de la API real."""
    comprador = item.get("Comprador", {}) or {}
    fechas = item.get("Fechas", {}) or {}

    codigo = item.get("CodigoExterno", "")
    titulo = item.get("Nombre", "")
    organismo = comprador.get("NombreOrganismo") or comprador.get("NombreUnidad") or ""

    fecha_pub = fechas.get("FechaPublicacion", "")
    fecha_cierre = fechas.get("FechaCierre") or item.get("FechaCierre", "")
    estado = item.get("Estado", "Publicada")
    descripcion = item.get("Descripcion", "")

    if fecha_pub and "T" in fecha_pub:
        fecha_pub = fecha_pub.split("T")[0]
    if fecha_cierre and "T" in fecha_cierre:
        fecha_cierre = fecha_cierre.split("T")[0]

    return {
        "codigo_licitacion": str(codigo),
        "titulo": titulo,
        "organismo": organismo,
        "fecha_publicacion": fecha_pub if fecha_pub else None,
        "fecha_cierre": fecha_cierre if fecha_cierre else None,
        "estado": estado,
        "descripcion": descripcion,
        "palabras_clave": [],
        "monto_estimado": item.get("MontoEstimado"),
        "region": comprador.get("RegionUnidad"),
        "comuna": comprador.get("ComunaUnidad"),
        "unidad_compra": comprador.get("NombreUnidad"),
    }


def es_rm(region: Optional[str]) -> bool:
    return bool(region) and REGION_RM in region.lower()


def filtrar_por_region(codigos: List[str]) -> List[Dict]:
    """Pide el detalle de cada código y devuelve solo los de la Región Metropolitana."""
    rm = []
    for i, codigo in enumerate(codigos, 1):
        try:
            data = _detalle_licitacion(codigo)
        except Exception as e:
            print(f"❌ Error obteniendo detalle de {codigo}: {e}", file=sys.stderr)
            continue

        listado = data.get("Listado") or []
        if not listado:
            continue

        campos = extraer_campos_licitacion(listado[0])
        marca = "🟢 RM" if es_rm(campos["region"]) else "⚪"
        print(f"   [{i}/{len(codigos)}] {marca} {codigo} — {campos['region'] or 'sin región'}")

        if es_rm(campos["region"]):
            rm.append(campos)

        time.sleep(PAUSA_ENTRE_REQUESTS)

    return rm


def generar_idempotency_key(codigo: str) -> str:
    return hashlib.md5(codigo.encode()).hexdigest()


def guardar_licitaciones(licitaciones: List[Dict]) -> int:
    if not licitaciones:
        return 0

    db = DatabaseManager().get_service_client()
    nuevos = 0
    errores = 0

    for lic in licitaciones:
        codigo = lic["codigo_licitacion"]
        if not codigo:
            continue

        key = generar_idempotency_key(codigo)

        existing = db.table("licitaciones").select("id").eq("codigo_licitacion", codigo).execute()
        if existing.data:
            continue
        existing = db.table("licitaciones").select("id").eq("idempotency_key", key).execute()
        if existing.data:
            continue

        data = {
            "codigo_licitacion": codigo,
            "titulo": lic["titulo"],
            "organismo": lic["organismo"],
            "fecha_publicacion": lic["fecha_publicacion"],
            "fecha_cierre": lic["fecha_cierre"],
            "estado": lic["estado"],
            "descripcion": lic["descripcion"],
            "palabras_clave": lic["palabras_clave"],
            "monto_estimado": lic.get("monto_estimado"),
            "region": lic.get("region"),
            "comuna": lic.get("comuna"),
            "unidad_compra": lic.get("unidad_compra"),
            "idempotency_key": key,
        }

        try:
            db.table("licitaciones").insert(data).execute()
            nuevos += 1
            print(f"✅ Insertada: {codigo} - {lic['titulo'][:50]}...")
        except Exception as e:
            errores += 1
            print(f"❌ Error insertando {codigo}: {e}", file=sys.stderr)

    print(f"📊 Resumen: {nuevos} nuevas, {errores} errores")
    return nuevos


def verificar_estado():
    db = DatabaseManager().get_service_client()
    count = db.table("licitaciones").select("id", count="exact").ilike("region", f"%{REGION_RM}%").execute()
    print(f"📊 Total licitaciones RM en BD: {count.count}")

    ultimas = db.table("licitaciones").select("codigo_licitacion, titulo, region, fecha_publicacion") \
        .ilike("region", f"%{REGION_RM}%").order("created_at", desc=True).limit(5).execute()
    print("📋 Últimas 5 RM:")
    for reg in ultimas.data:
        print(f"  - {reg['codigo_licitacion']}: {reg['titulo'][:50]}... ({reg['region']})")


def main():
    parser = argparse.ArgumentParser(description="Scraper de licitaciones de la Región Metropolitana")
    parser.add_argument("--cron", action="store_true", help="Ejecuta la actualización completa")
    parser.add_argument("--check", action="store_true", help="Verifica el estado actual (solo RM)")
    parser.add_argument("--dias", type=int, default=3, help="Días hacia atrás a consultar (default: 3)")
    parser.add_argument("--limite", type=int, default=50, help="Máximo de códigos a inspeccionar en detalle (default: 50)")
    args = parser.parse_args()

    if args.check:
        verificar_estado()
        return

    if args.cron:
        print(f"🔍 Buscando candidatos de los últimos {args.dias} días (máx. {args.limite})...")
        codigos = obtener_codigos_candidatos(dias_atras=args.dias, limite=args.limite)

        if not codigos:
            print("⚠️ No se obtuvieron códigos candidatos. Verifica la conexión a la API.")
            return

        print(f"✅ {len(codigos)} códigos candidatos. Consultando detalle para filtrar por región...")
        licitaciones_rm = filtrar_por_region(codigos)

        print(f"\n📊 {len(licitaciones_rm)} de {len(codigos)} son de Región Metropolitana")

        if licitaciones_rm:
            nuevos = guardar_licitaciones(licitaciones_rm)
            print(f"📥 {nuevos} nuevas licitaciones RM guardadas.")
        verificar_estado()
    else:
        print("⚠️ Usa --cron para actualizar o --check para ver estado.")


if __name__ == "__main__":
    main()
