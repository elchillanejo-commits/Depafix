#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Verifica las partidas registradas en proyecto_materiales por proyecto."""

import argparse
import os
import sys

from dotenv import load_dotenv
from supabase import create_client

load_dotenv()


def main():
    parser = argparse.ArgumentParser(description="Verifica materiales por proyecto.")
    parser.add_argument("--proyecto", required=True, help="Codigo del proyecto")
    args = parser.parse_args()

    url = os.getenv("SUPABASE_URL", "").strip()
    key = (
        os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
        or os.getenv("SUPABASE_KEY", "").strip()
    )
    if not url or not key:
        print("Faltan SUPABASE_URL y SUPABASE_SERVICE_ROLE_KEY en .env")
        return 1

    cliente = create_client(url, key)
    try:
        respuesta = (
            cliente.table("proyecto_materiales")
            .select(
                "material_sku,descripcion,cantidad_aprobada,"
                "precio_unitario_real_clp,precio_unitario_cliente_clp,total_cliente_clp"
            )
            .eq("proyecto_codigo", args.proyecto)
            .order("id")
            .execute()
        )
    except Exception as error:
        print(f"Error consultando proyecto_materiales: {error}")
        return 1

    filas = respuesta.data or []
    if not filas:
        print(f"No hay materiales registrados para {args.proyecto}.")
        return 0

    print(f"{'SKU':<14} {'CANT':>8} {'REAL':>12} {'CLIENTE':>12} {'TOTAL':>14}  DESCRIPCION")
    print("-" * 100)
    for fila in filas:
        print(
            f"{str(fila.get('material_sku') or ''):<14} "
            f"{float(fila.get('cantidad_aprobada') or 0):>8.2f} "
            f"{float(fila.get('precio_unitario_real_clp') or 0):>12,.0f} "
            f"{float(fila.get('precio_unitario_cliente_clp') or 0):>12,.0f} "
            f"{float(fila.get('total_cliente_clp') or 0):>14,.0f}  "
            f"{fila.get('descripcion') or ''}"
        )
    print("-" * 100)
    print(f"TOTAL PARTIDAS: {len(filas)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
