#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Scraper de Mercado Público con soporte para --fecha (parámetro nativo de la API).
"""

import os, sys, json, time, argparse, logging, re
from pathlib import Path
from dotenv import load_dotenv
import requests

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / "config" / ".env"
if ENV_PATH.exists():
    load_dotenv(ENV_PATH)

API_KEY = os.getenv("MERCADO_PUBLICO_API_KEY")
if not API_KEY:
    print("❌ MERCADO_PUBLICO_API_KEY no configurada en .env")
    sys.exit(1)

BASE_URL = "https://api.mercadopublico.cl/servicios/v1/publico/licitaciones.json"
DETALLE_URL = "https://api.mercadopublico.cl/servicios/v1/publico/licitacion.json"

def fetch_licitaciones(estado="adjudicada", limite=20, fecha=None):
    """Obtiene listado de licitaciones por estado y fecha (opcional)."""
    params = {"ticket": API_KEY, "estado": estado, "formato": "json"}
    if fecha:
        params["fecha"] = fecha  # <--- Parámetro nativo de la API
    for intento in range(5):
        try:
            resp = requests.get(BASE_URL, params=params, timeout=30)
            if resp.status_code == 429:
                wait = (2 ** intento) * 2
                print(f"⏳ Rate limit (429). Esperando {wait}s...")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            data = resp.json()
            listado = data.get("Listado") or data.get("listado") or data
            if isinstance(listado, list):
                return listado[:limite]
            if isinstance(listado, dict):
                return listado.get("licitacion", [])[:limite]
            return []
        except Exception as e:
            if intento == 4:
                raise
            print(f"⚠️ Error {e}, reintentando...")
            time.sleep(1)
    return []

def fetch_detalle(codigo):
    """Obtiene detalle de licitación por código."""
    params = {"ticket": API_KEY, "codigo": codigo, "formato": "json"}
    for intento in range(3):
        try:
            resp = requests.get(DETALLE_URL, params=params, timeout=30)
            if resp.status_code == 429:
                wait = (2 ** intento) * 2
                print(f"⏳ Rate limit (429). Esperando {wait}s...")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            if intento == 2:
                raise
            time.sleep(1)
    return {}

def extraer_precios(detalle):
    """Extrae precios unitarios y proveedores del detalle."""
    resultados = []
    codigo = detalle.get("Codigo") or detalle.get("CodigoExterno")
    if not codigo:
        return resultados
    items = detalle.get("Items", {}).get("Listado", [])
    if not items:
        items = detalle.get("Items", {}).get("item", [])
    for item in items:
        nombre = item.get("Nombre") or item.get("Descripcion") or ""
        adjudicacion = item.get("Adjudicacion", {})
        if not adjudicacion:
            adjudicacion = item.get("adjudicacion", {})
        if adjudicacion:
            precio = adjudicacion.get("MontoUnitario") or adjudicacion.get("Monto")
            proveedor = adjudicacion.get("NombreProveedor") or adjudicacion.get("Proveedor")
            if precio and float(precio) > 0:
                resultados.append({
                    "codigo": codigo,
                    "nombre": nombre.strip(),
                    "precio_unitario": float(precio),
                    "proveedor": proveedor or "Desconocido",
                    "fecha": adjudicacion.get("Fecha") or detalle.get("Fecha")
                })
    return resultados

def filtrar_por_rubro(licitaciones, rubro):
    """Filtra licitaciones que contengan el rubro en nombre o descripción."""
    rubro_lower = rubro.lower()
    filtradas = []
    for lic in licitaciones:
        nombre = lic.get("Nombre", "").lower()
        desc = lic.get("Descripcion", "").lower()
        if rubro_lower in nombre or rubro_lower in desc:
            filtradas.append(lic)
    return filtradas

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rubro", help="Filtrar por rubro (texto en nombre/descripción)")
    parser.add_argument("--limite", type=int, default=20)
    parser.add_argument("--salida", default="precios.json")
    parser.add_argument("--estado", default="adjudicada")
    parser.add_argument("--fecha", help="Fecha específica (YYYY-MM-DD)")  # <--- AHORA SÍ
    args = parser.parse_args()

    print(f"🔍 Buscando licitaciones estado={args.estado} (límite {args.limite})...")
    if args.fecha:
        print(f"📅 Fecha específica: {args.fecha}")
    
    licitaciones = fetch_licitaciones(estado=args.estado, limite=args.limite * 3, fecha=args.fecha)

    if args.rubro:
        print(f"📌 Filtrando por rubro: '{args.rubro}'")
        licitaciones = filtrar_por_rubro(licitaciones, args.rubro)
        print(f"✅ Encontradas {len(licitaciones)} coincidencias.")

    if not licitaciones:
        print("⚠️ No se encontraron licitaciones.")
        return

    todos_precios = []
    for idx, lic in enumerate(licitaciones[:args.limite], 1):
        codigo = lic.get("Codigo") or lic.get("CodigoExterno")
        if not codigo:
            continue
        print(f"📄 Procesando {idx}/{min(len(licitaciones), args.limite)}: {codigo}")
        try:
            detalle = fetch_detalle(codigo)
            precios = extraer_precios(detalle)
            todos_precios.extend(precios)
            time.sleep(0.5)
        except Exception as e:
            print(f"⚠️ Error con {codigo}: {e}")

    print(f"💰 Extraídos {len(todos_precios)} precios unitarios.")
    with open(args.salida, "w", encoding="utf-8") as f:
        json.dump(todos_precios, f, indent=2, ensure_ascii=False)
    print(f"✅ Guardado en {args.salida}")

    if todos_precios:
        print("\n📋 Primeros 5 materiales:")
        for item in todos_precios[:5]:
            print(f"  - {item['nombre']} → ${item['precio_unitario']:,.0f} ({item['proveedor']})")

if __name__ == "__main__":
    main()
