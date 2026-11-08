#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
seed_precios.py — Carga el catálogo de materiales desde un Excel a Supabase.

Lee `materiales_catalogo.xlsx` con columnas: SKU, Descripción, Unidad, Precio, Proveedor
e inserta cada fila en la tabla `materiales_catalogo` de Supabase.
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from supabase import create_client
import pandas as pd

EXCEL_PATH = Path("materiales_catalogo.xlsx")
TABLA = "materiales_catalogo"

load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = (
    os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    or os.getenv("SUPABASE_KEY")
)

if not SUPABASE_URL or not SUPABASE_KEY:
    print("[ERROR] Faltan credenciales de Supabase en el .env")
    sys.exit(1)

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


def seed_precios(ruta=EXCEL_PATH, tabla=TABLA, lote=50):
    if not ruta.exists():
        print(f"[ERROR] No existe el archivo: {ruta}")
        sys.exit(1)

    df = pd.read_excel(ruta)
    columnas_requeridas = {"SKU", "Descripción", "Unidad", "Precio", "Proveedor"}
    faltantes = columnas_requeridas - set(df.columns)
    if faltantes:
        print(f"[ERROR] Columnas faltantes en el Excel: {faltantes}")
        print(f"Columnas encontradas: {list(df.columns)}")
        sys.exit(1)

    filas = df.to_dict(orient="records")
    total = len(filas)
    print(f"📊 {total} fila(s) encontradas en {ruta.name}")

    insertados = 0
    errores = 0

    for i in range(0, total, lote):
        bloque = filas[i : i + lote]
        payload = []
        for fila in bloque:
            sku = str(fila["SKU"]).strip() if pd.notna(fila["SKU"]) else ""
            descripcion = str(fila["Descripción"]).strip() if pd.notna(fila["Descripción"]) else ""
            unidad = str(fila["Unidad"]).strip() if pd.notna(fila["Unidad"]) else ""
            precio = float(fila["Precio"]) if pd.notna(fila["Precio"]) else 0.0
            proveedor = str(fila["Proveedor"]).strip() if pd.notna(fila["Proveedor"]) else ""

            payload.append({
                "sku": sku,
                "descripcion": descripcion,
                "unidad": unidad,
                "precio": precio,
                "proveedor": proveedor,
            })

        try:
            supabase.table(tabla).insert(payload).execute()
            insertados += len(payload)
            print(f"  ✅ Lote {i//lote + 1}: {len(payload)} fila(s) insertada(s)")
        except Exception as error:
            errores += len(payload)
            print(f"  ❌ Lote {i//lote + 1} falló: {str(error)[:120]}")
            # Reintento uno a uno
            for fila in bloque:
                sku = str(fila["SKU"]).strip() if pd.notna(fila["SKU"]) else ""
                descripcion = str(fila["Descripción"]).strip() if pd.notna(fila["Descripción"]) else ""
                unidad = str(fila["Unidad"]).strip() if pd.notna(fila["Unidad"]) else ""
                precio = float(fila["Precio"]) if pd.notna(fila["Precio"]) else 0.0
                proveedor = str(fila["Proveedor"]).strip() if pd.notna(fila["Proveedor"]) else ""

                try:
                    supabase.table(tabla).insert({
                        "sku": sku,
                        "descripcion": descripcion,
                        "unidad": unidad,
                        "precio": precio,
                        "proveedor": proveedor,
                    }).execute()
                    insertados += 1
                    errores -= 1
                except Exception as error_fila:
                    print(f"      ❌ SKU {sku}: {str(error_fila)[:120]}")

    print(f"\n📈 Resumen: {insertados} insertado(s), {errores} error(es).")


if __name__ == "__main__":
    seed_precios()
