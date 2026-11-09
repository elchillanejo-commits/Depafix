#!/usr/bin/env python3
# -*- coding: utf-8 :-
"""Motor de Cotización DepaFix — pinturas.

Fórmulas:
    unidades_teoricas = superficie_m2 / rendimiento
    unidades_con_desperdicio = unidades_teoricas * (1 + desperdicio_pct/100)
    unidades_comerciales = ceil(unidades_con_desperdicio)
    costo_directo = unidades_comerciales * precio_neto_unitario
    precio_venta_neto = costo_directo / (1 - MARGEN)
    iva = precio_venta_neto * IVA
"""

import argparse
import json
import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

import uuid

from dotenv import load_dotenv
from supabase import create_client

# Constantes
MARGEN = 0.30
DESPERDICIO = 0.10
IVA = 0.19
MONEDA = "CLP"

# Cargar variables de entorno
def cargar_env() -> None:
    candidatos = [
        Path(__file__).resolve().parents[2] / ".env",
        Path.home() / "DepaFix_Maestro" / ".env",
        Path.cwd() / ".env",
    ]
    for ruta in candidatos:
        if ruta.exists():
            load_dotenv(ruta)
            return
    load_dotenv()

# Instancia de Supabase
def get_supabase():
    cargar_env()
    url = os.getenv("SUPABASE_URL")
    key = (
        os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        or os.getenv("SUPABASE_KEY")
        or os.getenv("SUPABASE_ANON_KEY")
    )
    if not url or not key:
        raise RuntimeError("Faltan SUPABASE_URL y SUPABASE_SERVICE_ROLE_KEY en .env")
    return create_client(url, key)

# Buscar producto por SKU
def _buscar_producto(sb, sku: str) -> Dict[str, Any]:
    exacto = (
        sb.table("productos")
        .select("id,sku,descripcion,unidad,categoria")
        .eq("sku", sku)
        .limit(1)
        .execute()
    )
    if exacto.data:
        return exacto.data[0]

    alias = (
        sb.table("precios_historial")
        .select("producto_id,url_producto")
        .like("url_producto", f"%{sku}%")
        .order("fecha_scrapeo", desc=True)
        .limit(1)
        .execute()
    )
    if alias.data:
        encontrado = (
            sb.table("productos")
            .select("id,sku,descripcion,unidad,categoria")
            .eq("id", alias.data[0]["producto_id"])
            .limit(1)
            .execute()
        )
        if encontrado.data:
            return encontrado.data[0]

    raise ValueError(f"SKU no encontrado en productos: {sku}")

# Obtener último precio registrado
def obtener_ultimo_precio(sku: str) -> Dict[str, Any]:
    sb = get_supabase()
    prod = _buscar_producto(sb, sku)

    precio = (
        sb.table("precios_historial")
        .select("precio_neto,precio_lista,url_producto,fecha_scrapeo")
        .eq("producto_id", prod["id"])
        .eq("es_valido", True)
        .gt("precio_neto", 0)
        .order("fecha_scrapeo", desc=True)
        .limit(1)
        .execute()
    )
    if not precio.data:
        raise ValueError(f"Sin precios_historial para el SKU {sku}")

    reg = precio.data[0]
    lista = float(reg["precio_lista"])
    neto = round(lista / (1 + IVA))
    return {
        "producto": prod,
        "sku_solicitado": sku,
        "precio_neto": neto,
        "precio_lista": lista,
        "url_producto": reg.get("url_producto"),
        "fecha_scrapeo": reg.get("fecha_scrapeo"),
    }

# ID único de cotización
def _id_cotizacion() -> str:
    marca = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return f"COT-{marca}-{uuid.uuid4().hex[:6].upper()}"

# Cargar rendimientos materiales desde JSON
def load_material_rendimientos() -> Dict[str, Dict[str, float]]:
    import json
    # Ruta correcta: /home/ibar/DepaFix_Maestro/src/data/rendimientos_materiales.json
    ruta = Path(__file__).resolve().parents[1] / "data" / "rendimientos_materiales.json"
    with open(ruta, "r", encoding="utf-8") as f:
        data = json.load(f)
    rendimientos = {}
    for item in data:
        nombre = item["material"]
        rendimientos[nombre] = {
            "rendimiento": float(item["rendimiento_m2_o_ml"]),
            "desperdicio_pct": float(item["desperdicio_sugerido_pct"]),
        }
    return rendimientos

# Generar cotización
def generar_cotizacion(superficie_m2: float, sku: str) -> Dict[str, Any]:
    if superficie_m2 <= 0:
        raise ValueError("superficie_m2 debe ser mayor que 0")

    precio = obtener_ultimo_precio(sku)
    prod = precio["producto"]
    precio_neto_unitario = float(precio["precio_neto"])
    precio_lista_unitario = float(precio["precio_lista"])

    # Determinar material a partir de la categoría del producto
    material_name = prod.get("categoria", "").strip()
    if not material_name:
        raise ValueError(f"El producto SKU {sku} no tiene categoría definida.")

    # Cargar tabla de rendimientos
    material_rendimientos = load_material_rendimientos()
    # Buscar coincidencia case‑insensitive
    match_key = None
    for key, val in material_rendimientos.items():
        if key.lower() == material_name.lower():
            match_key = key
            break
    if match_key is None:
        raise ValueError(f"Material '{material_name}' no encontrado en rendimientos_materiales.json")

    rendimiento = material_rendimientos[match_key]["rendimiento"]          # m2 (o ml) por unidad
    desperdicio_pct = material_rendimientos[match_key]["desperdicio_pct"]  # %

    # Cálculo de unidades necesarias
    unidades_teoricas = superficie_m2 / rendimiento
    unidades_con_desperdicio = unidades_teoricas * (1 + desperdicio_pct / 100)
    unidades_comerciales = math.ceil(unidades_con_desperdicio)

    # Costos y precios
    costo_directo = round(unidades_comerciales * precio_neto_unitario, 2)
    precio_venta_neto = round(costo_directo / (1 - MARGEN), 2)
    iva = round(precio_venta_neto * IVA, 2)
    precio_venta_con_iva = round(precio_venta_neto + iva, 2)
    utilidad = round(precio_venta_neto - costo_directo, 2)

    # Construir partida
    partida = {
        "item": 1,
        "sku": prod["sku"],
        "descripcion": prod["descripcion"],
        "unidad": prod.get("unidad", "unidad"),
        "superficie_m2": superficie_m2,
        "rendimiento_m2_o_ml": rendimiento,
        "galones_teoricos": round(unidades_teoricas, 4),
        "galones_con_desperdicio": round(unidades_con_desperdicio, 4),
        "galones_a_comprar": unidades_comerciales,
        "precio_unitario_neto": precio_neto_unitario,
        "precio_unitario_lista": precio_lista_unitario,
        "costo_directo_neto": costo_directo,
        "precio_venta_neto": precio_venta_neto,
        "iva": iva,
        "precio_venta_con_iva": precio_venta_con_iva,
    }

    # Parámetros globales (usar datos del primer material)
    param_globales = {
        "sku": prod["sku"],
        "sku_solicitado": precio["sku_solicitado"],
        "descripcion": prod["descripcion"],
        "categoria": prod.get("categoria"),
        "superficie_m2": superficie_m2,
        "rendimiento_m2_por_galon": rendimiento,
        "desperdicio_pct": desperdicio_pct,
        "margen_pct": MARGEN * 100,
        "iva_pct": IVA * 100,
        "moneda": MONEDA,
        "precio_unitario_neto": precio_neto_unitario,
        "precio_unitario_lista": precio_lista_unitario,
        "precio_fuente_url": precio.get("url_producto"),
        "precio_fecha_scrapeo": precio.get("fecha_scrapeo"),
        "fecha_cotizacion": datetime.now(timezone.utc).isoformat(),
    }

    return {
        "id_cotizacion": _id_cotizacion(),
        "parametros_globales": param_globales,
        "partidas": [partida],
        "resumen_financiero": {
            "costo_directo_neto_total": costo_directo,
            "precio_venta_neto_total": precio_venta_neto,
            "iva_total": iva,
            "precio_venta_con_iva_total": precio_venta_con_iva,
            "utilidad_neta_total": utilidad,
            "margen_utilidad_pct": MARGEN * 100,
        },
    }

def main() -> int:
    parser = argparse.ArgumentParser(description="Motor de cotización DepaFix")
    parser.add_argument("superficie_m2", type=float, help="Superficie en m2")
    parser.add_argument("sku", help="SKU del producto en Supabase")
    args = parser.parse_args()

    cotizacion = generar_cotizacion(args.superficie_m2, args.sku)
    print(json.dumps(cotizacion, ensure_ascii=False, indent=2, default=str))
    return 0

if __name__ == "__main__":
    sys.exit(main())