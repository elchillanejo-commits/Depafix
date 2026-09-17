#!/usr/bin/env python3
"""Agente abogado para analisis legal"""
import argparse
import json
import sys
sys.path.insert(0, '/home/ibar/Proyectos/DepaFix')
from core.db_manager import DatabaseManager

def analizar_licitacion(licitacion_id: int):
    db = DatabaseManager().get_service_client()
    lic = db.table("licitaciones").select("*").eq("id", licitacion_id).execute()
    if not lic.data: return {"error": "No encontrada"}
    lic = lic.data[0]
    texto = f"{lic.get('titulo', '')} {lic.get('descripcion', '')}"
    palabras_riesgo = ["indemnizacion", "multa", "penalizacion", "arbitraje", "garantia", "seguro"]
    clausulas = [p for p in palabras_riesgo if p.lower() in texto.lower()]
    riesgo = "Alto" if len(clausulas) >= 3 else "Medio" if len(clausulas) >= 1 else "Bajo"
    return {
        "licitacion_id": licitacion_id,
        "riesgo_legal": riesgo,
        "clausulas_riesgosas": clausulas,
        "recomendaciones": ["Revisar clausulas" if clausulas else "Sin observaciones"],
        "foda": {"fortalezas": ["Financiamiento asegurado"], "debilidades": [f"{len(clausulas)} clausulas riesgosas"], "oportunidades": ["Relacion a largo plazo"], "amenazas": ["Retrasos en pagos"]},
        "puntaje_total": 80 - (len(clausulas) * 5)
    }

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--licitacion", type=int, required=True)
    args = parser.parse_args()
    analisis = analizar_licitacion(args.licitacion)
    print(f"\n⚖️ RIESGO: {analisis['riesgo_legal']}")
    print(f"📋 Clausulas: {', '.join(analisis['clausulas_riesgosas']) or 'Ninguna'}")
    print(f"📌 FODA: {json.dumps(analisis['foda'], indent=2, ensure_ascii=False)}")

if __name__ == "__main__":
    main()
