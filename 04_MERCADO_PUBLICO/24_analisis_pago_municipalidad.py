#!/usr/bin/env python3
"""
Consulta historial de pagos de una municipalidad/organismo
"""

import sys
sys.path.insert(0, '/home/ibar/Proyectos/DepaFix')
from core.db_manager import DatabaseManager

def analizar_historial_pagos(organismo: str) -> dict:
    db = DatabaseManager().get_service_client()
    result = db.table("historial_pagos").select("*").ilike("organismo", f"%{organismo}%").execute()
    if not result.data:
        return {"total": 0, "promedio_mora": None, "clasificacion": "Sin historial"}
    
    moras = [r.get("dias_mora", 0) for r in result.data if r.get("dias_mora")]
    promedio = sum(moras) / len(moras) if moras else 0
    if promedio <= 30:
        clasificacion = "🟢 Excelente pagador"
    elif promedio <= 45:
        clasificacion = "🟡 Pagador regular"
    else:
        clasificacion = "🔴 Mal pagador - Riesgo alto"
    
    return {
        "total": len(result.data),
        "promedio_mora": promedio,
        "clasificacion": clasificacion,
        "ultimos_pagos": result.data[:3]
    }

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--organismo", type=str, required=True)
    args = parser.parse_args()
    resultado = analizar_historial_pagos(args.organismo)
    print(f"📊 Historial de {args.organismo}:")
    print(f"   Registros: {resultado['total']}")
    if resultado["promedio_mora"] is not None:
        print(f"   Mora promedio: {resultado['promedio_mora']:.0f} días")
    print(f"   Clasificación: {resultado['clasificacion']}")

if __name__ == "__main__":
    main()
