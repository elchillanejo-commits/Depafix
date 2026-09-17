#!/usr/bin/env python3
"""Precios de referencia de materiales"""
import argparse
import sys
sys.path.insert(0, '/home/ibar/Proyectos/DepaFix')
from core.db_manager import DatabaseManager

def buscar_precios(productos: list):
    db = DatabaseManager().get_service_client()
    resultados = []
    for p in productos:
        result = db.table("precios_referencia").select("*").ilike("producto", f"%{p}%").execute()
        if result.data:
            resultados.extend(result.data)
    return resultados

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--productos", type=str, nargs="+", required=True)
    args = parser.parse_args()
    resultados = buscar_precios(args.productos)
    if not resultados:
        print("⚠️ No se encontraron precios para esos productos")
        return
    for r in resultados:
        print(f"\n📦 {r['producto']}:")
        print(f"  Sodimac: ${r.get('precio_sodimac', 'N/A')}")
        print(f"  Imperial: ${r.get('precio_imperial', 'N/A')}")
        print(f"  Yolito: ${r.get('precio_yolito', 'N/A')}")
        print(f"  Promedio: ${r.get('precio_promedio', 'N/A')}")

if __name__ == "__main__":
    main()
