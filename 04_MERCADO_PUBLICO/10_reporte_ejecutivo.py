#!/usr/bin/env python3
"""
Reporte ejecutivo FODA para contratista.
Genera un análisis completo de una licitación con recomendaciones.
"""

import argparse
import json
from datetime import datetime
from typing import Dict, List
from core.db_manager import DatabaseManager

def obtener_licitacion(licitacion_id: int) -> Dict:
    """Obtiene una licitación por ID."""
    db = DatabaseManager().get_service_client()
    result = db.table("licitaciones").select("*").eq("id", licitacion_id).execute()
    if not result.data:
        return None
    return result.data[0]

def obtener_analisis_legal(licitacion_id: int) -> Dict:
    """Obtiene el análisis legal de una licitación si existe."""
    db = DatabaseManager().get_service_client()
    result = db.table("analisis_licitaciones").select("*").eq("licitacion_id", licitacion_id).execute()
    if not result.data:
        return None
    return result.data[0]

def obtener_historial_organismo(organismo: str) -> Dict:
    """Obtiene el historial de pagos de un organismo."""
    db = DatabaseManager().get_service_client()
    result = db.table("historial_pagos").select("*").ilike("organismo", f"%{organismo}%").execute()
    if not result.data:
        return {"total": 0, "promedio_mora": 0, "clasificacion": "Sin historial"}
    
    total = len(result.data)
    moras = [r.get("dias_mora", 0) for r in result.data if r.get("dias_mora")]
    promedio_mora = sum(moras) / len(moras) if moras else 0
    
    if promedio_mora <= 15:
        clasificacion = "🟢 Buen pagador"
    elif promedio_mora <= 30:
        clasificacion = "🟡 Pagador regular"
    else:
        clasificacion = "🔴 Mal pagador"
    
    return {
        "total": total,
        "promedio_mora": promedio_mora,
        "clasificacion": clasificacion
    }

def generar_foda(licitacion: Dict, analisis: Dict = None) -> Dict:
    """Genera análisis FODA de la licitación."""
    foda = {
        "fortalezas": [],
        "debilidades": [],
        "oportunidades": [],
        "amenazas": []
    }
    
    if licitacion.get("monto_estimado"):
        foda["fortalezas"].append(f"Monto estimado: ${licitacion['monto_estimado']:,.0f}")
    foda["fortalezas"].append("Licitacion publica con proceso transparente")
    if licitacion.get("region") == "Metropolitana":
        foda["fortalezas"].append("Ubicacion en Region Metropolitana - logistica favorable")
    
    if analisis and analisis.get("clausulas_riesgosas"):
        foda["debilidades"].append(f"{len(analisis['clausulas_riesgosas'])} clausulas riesgosas detectadas")
    if not licitacion.get("fecha_cierre"):
        foda["debilidades"].append("Fecha de cierre no especificada")
    
    foda["oportunidades"].append("Posibilidad de establecer relacion comercial a largo plazo")
    foda["oportunidades"].append("Acceso a financiamiento bancario con licitacion como respaldo")
    
    foda["amenazas"].append("Competencia de empresas con mayor experiencia")
    foda["amenazas"].append("Posibles retrasos en pagos por parte del organismo")

    return foda

def generar_recomendaciones(licitacion: Dict, analisis: Dict = None, historial: Dict = None) -> List[str]:
    """Genera recomendaciones basadas en el analisis."""
    recomendaciones = []
    
    recomendaciones.append("✅ Revisar detalladamente las bases administrativas")
    recomendaciones.append("✅ Verificar requisitos de garantia y seguros")
    
    if analisis and analisis.get("riesgo_legal") == "Alto":
        recomendaciones.append("⚠️ Se recomienda asesoria legal antes de presentar oferta")
    
    if historial and historial.get("promedio_mora", 0) > 30:
        recomendaciones.append(f"⚠️ Organismo con historial de mora ({historial['promedio_mora']:.0f} dias promedio) - considerar financiamiento propio")
    
    if licitacion.get("monto_estimado") and licitacion.get("monto_estimado") > 100000000:
        recomendaciones.append("💰 Monto significativo - considerar alianza estrategica")
    
    return recomendaciones

def generar_reporte(licitacion_id: int, contratista: str = None) -> Dict:
    """Genera el reporte ejecutivo completo."""
    licitacion = obtener_licitacion(licitacion_id)
    if not licitacion:
        return {"error": f"No se encontro licitacion con ID {licitacion_id}"}
    
    analisis = obtener_analisis_legal(licitacion_id)
    historial = obtener_historial_organismo(licitacion.get("organismo", ""))
    foda = generar_foda(licitacion, analisis)
    recomendaciones = generar_recomendaciones(licitacion, analisis, historial)
    
    riesgo_total = "🟢 BAJO"
    if analisis and analisis.get("riesgo_legal") == "Alto":
        riesgo_total = "🔴 ALTO"
    elif analisis and analisis.get("riesgo_legal") == "Medio":
        riesgo_total = "🟡 MEDIO"
    
    if historial.get("promedio_mora", 0) > 30:
        riesgo_total = "🔴 ALTO"
    
    return {
        "licitacion": licitacion,
        "contratista": contratista or "No especificado",
        "fecha_reporte": datetime.now().isoformat(),
        "analisis_legal": analisis,
        "historial_pagos": historial,
        "foda": foda,
        "recomendaciones": recomendaciones,
        "riesgo_total": riesgo_total,
        "puntaje_estimado": 100 - (10 if analisis and len(analisis.get("clausulas_riesgosas", [])) > 2 else 0) - (15 if historial.get("promedio_mora", 0) > 30 else 0)
    }

def imprimir_reporte(reporte: Dict):
    """Imprime el reporte en formato legible."""
    if "error" in reporte:
        print(f"❌ {reporte['error']}")
        return
    
    lic = reporte["licitacion"]
    
    print("\n" + "=" * 70)
    print("📋 REPORTE EJECUTIVO PARA CONTRATISTA")
    print("=" * 70)
    
    print(f"\n🏷️  LICITACION:")
    print(f"   Codigo: {lic.get('codigo_licitacion', 'N/A')}")
    print(f"   Titulo: {lic.get('titulo', 'Sin titulo')}")
    print(f"   Organismo: {lic.get('organismo', 'No especificado')}")
    if lic.get('monto_estimado'):
        print(f"   Monto: ${lic.get('monto_estimado'):,.0f}")
    else:
        print("   Monto: No especificado")
    print(f"   Region: {lic.get('region', 'No especificada')}")
    print(f"   Estado: {lic.get('estado', 'N/A')}")
    print(f"   Cierre: {lic.get('fecha_cierre', 'No especificada')}")
    
    print(f"\n📊 RIESGO TOTAL: {reporte['riesgo_total']}")
    print(f"📊 PUNTAJE ESTIMADO: {reporte['puntaje_estimado']}/100")
    
    print(f"\n📌 HISTORIAL DE PAGOS:")
    print(f"   Registros: {reporte['historial_pagos']['total']}")
    print(f"   Mora promedio: {reporte['historial_pagos']['promedio_mora']:.0f} dias")
    print(f"   Clasificacion: {reporte['historial_pagos']['clasificacion']}")
    
    print(f"\n📌 ANALISIS FODA:")
    for key, values in reporte["foda"].items():
        print(f"   {key.capitalize()}:")
        for value in values:
            print(f"     - {value}")
    
    print(f"\n💡 RECOMENDACIONES:")
    for rec in reporte["recomendaciones"]:
        print(f"   {rec}")
    
    print("\n" + "=" * 70)
    print(f"📅 Reporte generado: {reporte['fecha_reporte']}")
    print("=" * 70)

def guardar_reporte(reporte: Dict, contratista_id: int):
    """Guarda el reporte en Supabase."""
    db = DatabaseManager().get_service_client()
    db.table("reportes_contratista").insert({
        "contratista_id": contratista_id,
        "licitacion_id": reporte["licitacion"]["id"],
        "contenido": reporte,
        "formato": "JSON"
    }).execute()
    print("✅ Reporte guardado en Supabase")

def main():
    parser = argparse.ArgumentParser(description="Reporte ejecutivo FODA para contratista")
    parser.add_argument("--licitacion", type=int, required=True, help="ID de la licitacion")
    parser.add_argument("--contratista", type=str, help="Nombre del contratista")
    parser.add_argument("--contratista-id", type=int, help="ID del contratista en suscripciones")
    parser.add_argument("--guardar", action="store_true", help="Guardar reporte en Supabase")
    args = parser.parse_args()
    
    print("📋 Generando reporte ejecutivo...")
    reporte = generar_reporte(args.licitacion, args.contratista)
    imprimir_reporte(reporte)
    
    if args.guardar and args.contratista_id:
        guardar_reporte(reporte, args.contratista_id)
    elif args.guardar:
        print("\n⚠️ Para guardar necesitas --contratista-id")

if __name__ == "__main__":
    main()
