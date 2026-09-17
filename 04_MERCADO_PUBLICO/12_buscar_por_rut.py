#!/usr/bin/env python3
"""
Buscar licitaciones por RUT de empresa o contratista
"""

import argparse
import sys
sys.path.insert(0, '/home/ibar/Proyectos/DepaFix')
from core.db_manager import DatabaseManager

def buscar_por_rut(rut: str):
    """Busca licitaciones asociadas a un RUT específico"""
    db = DatabaseManager().get_service_client()
    
    # Buscar en licitaciones (si el RUT aparece en descripción)
    result = db.table("licitaciones") \
        .select("*") \
        .or_(f"descripcion.ilike.%{rut}%, titulo.ilike.%{rut}%") \
        .execute()
    
    return result.data

def buscar_por_empresa(nombre: str):
    """Busca licitaciones por nombre de empresa"""
    db = DatabaseManager().get_service_client()
    
    result = db.table("licitaciones") \
        .select("*") \
        .or_(f"organismo.ilike.%{nombre}%, titulo.ilike.%{nombre}%, descripcion.ilike.%{nombre}%") \
        .execute()
    
    return result.data

def main():
    parser = argparse.ArgumentParser(description="Buscar licitaciones por RUT o empresa")
    parser.add_argument("--rut", type=str, help="RUT de la empresa")
    parser.add_argument("--empresa", type=str, help="Nombre de la empresa")
    args = parser.parse_args()
    
    if args.rut:
        print(f"🔍 Buscando licitaciones con RUT: {args.rut}")
        resultados = buscar_por_rut(args.rut)
    elif args.empresa:
        print(f"🔍 Buscando licitaciones con empresa: {args.empresa}")
        resultados = buscar_por_empresa(args.empresa)
    else:
        print("⚠️ Usa --rut o --empresa")
        return
    
    print(f"📊 {len(resultados)} licitaciones encontradas")
    for lic in resultados[:20]:
        print(f"  - {lic.get('codigo_licitacion')}: {lic.get('titulo')[:60]}...")
        print(f"    Organismo: {lic.get('organismo')}")
        print(f"    Estado: {lic.get('estado')}")

if __name__ == "__main__":
    main()
