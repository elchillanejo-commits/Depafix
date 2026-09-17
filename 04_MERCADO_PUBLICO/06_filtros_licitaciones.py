#!/usr/bin/env python3
"""Filtros avanzados por monto y region"""
import argparse
import sys
sys.path.insert(0, '/home/ibar/Proyectos/DepaFix')
from core.db_manager import DatabaseManager

def filtrar_por_monto(min_monto: float = None, max_monto: float = None):
    db = DatabaseManager().get_service_client()
    query = db.table("licitaciones").select("*")
    if min_monto: query = query.gte("monto_estimado", min_monto)
    if max_monto: query = query.lte("monto_estimado", max_monto)
    return query.execute().data

def filtrar_por_region(region: str):
    db = DatabaseManager().get_service_client()
    return db.table("licitaciones").select("*").ilike("region", f"%{region}%").execute().data

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--region", type=str, help="Filtrar por region")
    parser.add_argument("--min-monto", type=float, help="Monto minimo")
    parser.add_argument("--max-monto", type=float, help="Monto maximo")
    args = parser.parse_args()
    resultados = []
    if args.region and (args.min_monto or args.max_monto):
        db = DatabaseManager().get_service_client()
        query = db.table("licitaciones").select("*").ilike("region", f"%{args.region}%")
        if args.min_monto: query = query.gte("monto_estimado", args.min_monto)
        if args.max_monto: query = query.lte("monto_estimado", args.max_monto)
        resultados = query.execute().data
    elif args.region:
        resultados = filtrar_por_region(args.region)
    elif args.min_monto or args.max_monto:
        resultados = filtrar_por_monto(args.min_monto, args.max_monto)
    else:
        print("⚠️ Usa --region, --min-monto o --max-monto")
        return
    print(f"📊 {len(resultados)} licitaciones encontradas")
    for lic in resultados:
        print(f"  - {lic['codigo_licitacion']}: {lic['titulo'][:50]}... (${lic.get('monto_estimado', 'N/A')})")

if __name__ == "__main__":
    main()
