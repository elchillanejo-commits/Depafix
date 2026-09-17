#!/usr/bin/env python3
"""
Costeador detallado con ítems reales y precios de referencia
"""

import sys
import json
sys.path.insert(0, '/home/ibar/Proyectos/DepaFix')
from core.db_manager import DatabaseManager

def obtener_precios_referencia():
    db = DatabaseManager().get_service_client()
    result = db.table("precios_referencia").select("*").execute()
    precios = {}
    for r in result.data:
        precios[r["producto"]] = r["precio_promedio"]
    return precios

def costear_items(items: list) -> dict:
    """Calcula costo total de una lista de items con cantidades"""
    precios = obtener_precios_referencia()
    total = 0
    detalle = []
    for item in items:
        producto = item.get("producto", "")
        cantidad = item.get("cantidad", 0)
        precio_unitario = precios.get(producto, 0) or item.get("precio_unitario", 0)
        subtotal = cantidad * precio_unitario
        total += subtotal
        detalle.append({
            "producto": producto,
            "cantidad": cantidad,
            "precio_unitario": precio_unitario,
            "subtotal": subtotal
        })
    return {"total": total, "detalle": detalle}

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--items", type=str, required=True, help="JSON con lista de items")
    args = parser.parse_args()
    
    try:
        items = json.loads(args.items)
    except:
        print("❌ Error: items debe ser un JSON válido")
        sys.exit(1)
    
    resultado = costear_items(items)
    print(f"💰 Costo total materiales: ${resultado['total']:,.0f}")
    print("\n📋 Detalle:")
    for d in resultado["detalle"]:
        print(f"  {d['producto']}: {d['cantidad']} x ${d['precio_unitario']:,.0f} = ${d['subtotal']:,.0f}")

if __name__ == "__main__":
    main()
