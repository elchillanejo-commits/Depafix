#!/usr/bin/env python3
"""Historial de pagos de municipalidades"""
import argparse
import sys
sys.path.insert(0, '/home/ibar/Proyectos/DepaFix')
from core.db_manager import DatabaseManager

def obtener_historial_pagos(organismo: str):
    db = DatabaseManager().get_service_client()
    return db.table("historial_pagos").select("*").ilike("organismo", f"%{organismo}%").order("fecha_pago", desc=True).execute().data

def calcular_promedio_mora(organismo: str):
    db = DatabaseManager().get_service_client()
    result = db.table("historial_pagos").select("dias_mora").ilike("organismo", f"%{organismo}%").execute()
    if not result.data: return 0
    moras = [r.get("dias_mora", 0) for r in result.data if r.get("dias_mora")]
    return sum(moras) / len(moras) if moras else 0

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--organismo", type=str, required=True)
    parser.add_argument("--clasificar", action="store_true")
    args = parser.parse_args()
    pagos = obtener_historial_pagos(args.organismo)
    print(f"📊 {args.organismo}: {len(pagos)} registros")
    for p in pagos[:10]:
        print(f"  - {p['fecha_pago']}: ${p['monto_pagado']} (Mora: {p.get('dias_mora', 0)} dias)")
    if args.clasificar:
        promedio = calcular_promedio_mora(args.organismo)
        if promedio <= 15:
            clasificacion = "🟢 Buen pagador"
        elif promedio <= 30:
            clasificacion = "🟡 Pagador regular"
        else:
            clasificacion = "🔴 Mal pagador"
        print(f"\n📌 Clasificacion: {clasificacion} (promedio {promedio:.0f} dias)")

if __name__ == "__main__":
    main()
