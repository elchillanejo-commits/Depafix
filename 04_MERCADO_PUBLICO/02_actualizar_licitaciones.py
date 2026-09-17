#!/usr/bin/env python3
"""
Actualiza la tabla licitaciones con datos reales de ChileCompra.
Usa la API pública de Mercado Público.
"""

import os
import sys
import time
import hashlib
import argparse
import requests
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from core.db_manager import DatabaseManager
from core.resiliencia import red_segura

load_dotenv(BASE_DIR / ".env")

# API real de Mercado Público (ChileCompra). Los dominios "apis.mercadopublico.cl"
# (RSS y v1) no existen -- devuelven 404. Auth vía query param `ticket`.
API_BASE = "https://api.mercadopublico.cl/servicios/v1/publico/licitaciones.json"
TICKET = os.getenv("MERCADO_PUBLICO_API_KEY")

# Pausa entre requests para evitar "Hemos detectado peticiones simultáneas" (Codigo 10500)
PAUSA_ENTRE_REQUESTS = 2.5


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


def obtener_licitaciones_activas(dias_atras: int = 7, limite: int = 100) -> List[Dict]:
    """
    Obtiene licitaciones publicadas de los últimos `dias_atras` días.

    La API no soporta un rango de fechas -- `fecha` es un día puntual -- así
    que se consulta día por día y se deduplica por CodigoExterno. El listado
    por fecha solo trae campos mínimos (Nombre/CodigoEstado/FechaCierre), así
    que se pide el detalle completo (Comprador, Fechas, MontoEstimado,
    Descripcion) por cada código encontrado.
    """
    if not TICKET:
        print("❌ Falta MERCADO_PUBLICO_API_KEY en .env", file=sys.stderr)
        return []

    codigos_vistos = set()
    for dias in range(dias_atras):
        fecha = (datetime.now() - timedelta(days=dias)).strftime("%d%m%Y")
        try:
            data = _listar_por_fecha(fecha, estado="publicada")
        except Exception as e:
            print(f"❌ Error consultando fecha={fecha}: {e}", file=sys.stderr)
            continue

        for item in data.get("Listado", []) or []:
            codigo = item.get("CodigoExterno")
            if codigo:
                codigos_vistos.add(codigo)
            if len(codigos_vistos) >= limite:
                break
        time.sleep(PAUSA_ENTRE_REQUESTS)
        if len(codigos_vistos) >= limite:
            break

    detalles = []
    for codigo in list(codigos_vistos)[:limite]:
        try:
            detalle = _detalle_licitacion(codigo)
        except Exception as e:
            print(f"❌ Error obteniendo detalle de {codigo}: {e}", file=sys.stderr)
            continue
        if detalle.get("Listado"):
            detalles.append(detalle["Listado"][0])
        time.sleep(PAUSA_ENTRE_REQUESTS)

    return detalles


def extraer_campos_licitacion(item: Dict) -> Dict:
    """
    Extrae los campos relevantes de un item de detalle (por `codigo`) de la
    API real de Mercado Público.
    """
    comprador = item.get("Comprador", {}) or {}
    fechas = item.get("Fechas", {}) or {}

    codigo = item.get("CodigoExterno", "")
    titulo = item.get("Nombre", "")
    organismo = comprador.get("NombreOrganismo") or comprador.get("NombreUnidad") or ""

    fecha_pub = fechas.get("FechaPublicacion", "")
    fecha_cierre = fechas.get("FechaCierre") or item.get("FechaCierre", "")
    estado = item.get("Estado", "Publicada")
    descripcion = item.get("Descripcion", "")

    # Limpiar fechas (vienen en formato ISO con hora)
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
        "palabras_clave": [],  # Se puede enriquecer después
        "monto_estimado": item.get("MontoEstimado"),
        "region": comprador.get("RegionUnidad"),
        "comuna": comprador.get("ComunaUnidad"),
        "unidad_compra": comprador.get("NombreUnidad"),
    }


def generar_idempotency_key(codigo: str) -> str:
    """Genera clave única para evitar duplicados."""
    return hashlib.md5(codigo.encode()).hexdigest()


def guardar_licitaciones(licitaciones: List[Dict]) -> int:
    """
    Guarda licitaciones en Supabase con idempotencia.
    Retorna el número de registros nuevos insertados.
    """
    if not licitaciones:
        return 0
    
    db = DatabaseManager().get_service_client()
    tabla = "licitaciones"
    nuevos = 0
    errores = 0
    
    for lic in licitaciones:
        codigo = lic["codigo_licitacion"]
        if not codigo:
            continue
            
        key = generar_idempotency_key(codigo)
        
        # Verificar si ya existe (por codigo_licitacion o idempotency_key)
        existing = db.table(tabla).select("id").eq("codigo_licitacion", codigo).execute()
        if existing.data:
            continue
            
        # Verificar por idempotency_key
        existing = db.table(tabla).select("id").eq("idempotency_key", key).execute()
        if existing.data:
            continue
        
        # Insertar
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
            "idempotency_key": key
        }
        
        try:
            db.table(tabla).insert(data).execute()
            nuevos += 1
            print(f"✅ Insertada: {codigo} - {lic['titulo'][:50]}...")
        except Exception as e:
            errores += 1
            print(f"❌ Error insertando {codigo}: {e}", file=sys.stderr)
    
    print(f"📊 Resumen: {nuevos} nuevas, {errores} errores")
    return nuevos


def verificar_estado():
    """Muestra el estado actual de la tabla."""
    db = DatabaseManager().get_service_client()
    count = db.table("licitaciones").select("id", count="exact").execute()
    print(f"📊 Total licitaciones en BD: {count.count}")
    
    # Últimas 5
    ultimas = db.table("licitaciones").select("codigo_licitacion, titulo, fecha_publicacion").order("created_at", desc=True).limit(5).execute()
    print("📋 Últimas 5:")
    for reg in ultimas.data:
        print(f"  - {reg['codigo_licitacion']}: {reg['titulo'][:50]}... ({reg['fecha_publicacion']})")


def main():
    parser = argparse.ArgumentParser(description="Actualiza licitaciones desde Mercado Público")
    parser.add_argument("--cron", action="store_true", help="Ejecuta actualización completa")
    parser.add_argument("--check", action="store_true", help="Verifica estado actual")
    parser.add_argument("--dias", type=int, default=7, help="Días hacia atrás a consultar (default: 7)")
    parser.add_argument("--limite", type=int, default=100, help="Límite de licitaciones (default: 100)")
    args = parser.parse_args()
    
    if args.check:
        verificar_estado()
        return
    
    if args.cron:
        print(f"🔍 Obteniendo licitaciones de los últimos {args.dias} días...")
        licitaciones = obtener_licitaciones_activas(dias_atras=args.dias, limite=args.limite)
        
        if not licitaciones:
            print("⚠️ No se obtuvieron licitaciones. Verifica la conexión a la API.")
            return
        
        print(f"✅ {len(licitaciones)} licitaciones obtenidas.")
        
        # Extraer campos
        datos = [extraer_campos_licitacion(lic) for lic in licitaciones]
        datos = [d for d in datos if d["codigo_licitacion"]]
        
        print(f"📝 {len(datos)} licitaciones válidas para guardar.")
        
        if datos:
            nuevos = guardar_licitaciones(datos)
            print(f"📥 {nuevos} nuevas licitaciones guardadas.")
            verificar_estado()
    else:
        print("⚠️ Usa --cron para actualizar o --check para ver estado.")


if __name__ == "__main__":
    main()
