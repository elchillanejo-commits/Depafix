#!/usr/bin/env python3
"""
Análisis profundo de licitaciones para contratistas
Evalúa: economía, viabilidad, pagos, estrategia de oferta
"""

import argparse
import sys
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any
sys.path.insert(0, '/home/ibar/Proyectos/DepaFix')
from core.db_manager import DatabaseManager

# Umbrales
MONTO_MIN = 10_000_000
MONTO_MAX = 50_000_000
UTILIDAD_MIN = 0.25  # 25% mínimo
DIAS_PAGO_IDEAL = 30
DIAS_PAGO_MAXIMO = 45

# Costos estimados por tipo de obra (porcentaje del monto)
COSTOS_ESTIMADOS = {
    "remodelacion": {"materiales": 0.40, "mano_obra": 0.35, "administrativo": 0.10, "impuestos": 0.05},
    "construccion": {"materiales": 0.45, "mano_obra": 0.30, "administrativo": 0.08, "impuestos": 0.05},
    "electricidad": {"materiales": 0.35, "mano_obra": 0.40, "administrativo": 0.10, "impuestos": 0.05},
    "gasfiteria": {"materiales": 0.35, "mano_obra": 0.40, "administrativo": 0.10, "impuestos": 0.05},
    "default": {"materiales": 0.40, "mano_obra": 0.35, "administrativo": 0.10, "impuestos": 0.05}
}

def formatear_monto(valor):
    """Formatea un monto o retorna 'N/A' si es None"""
    if valor is None:
        return "N/A"
    try:
        return f"${float(valor):,.0f}"
    except (ValueError, TypeError):
        return "N/A"

def obtener_licitacion(licitacion_id: int) -> Dict:
    """Obtiene datos de una licitación"""
    db = DatabaseManager().get_service_client()
    result = db.table("licitaciones").select("*").eq("id", licitacion_id).execute()
    if not result.data:
        return None
    return result.data[0]

def obtener_historial_pagos(organismo: str) -> Dict:
    """Obtiene historial de pagos del organismo"""
    db = DatabaseManager().get_service_client()
    result = db.table("historial_pagos").select("*").ilike("organismo", f"%{organismo}%").execute()
    if not result.data:
        return {"total": 0, "promedio_mora": None, "clasificacion": "Sin historial", "registros": []}
    
    moras = [r.get("dias_mora", 0) for r in result.data if r.get("dias_mora")]
    promedio = sum(moras) / len(moras) if moras else 0
    
    if promedio <= DIAS_PAGO_IDEAL:
        clasificacion = "🟢 Excelente pagador"
    elif promedio <= DIAS_PAGO_MAXIMO:
        clasificacion = "🟡 Pagador regular"
    else:
        clasificacion = "🔴 Mal pagador - Riesgo alto"
    
    return {
        "total": len(result.data),
        "promedio_mora": promedio,
        "clasificacion": clasificacion,
        "registros": result.data[:5]
    }

def analisis_economico(licitacion: Dict) -> Dict:
    """Análisis económico de la licitación"""
    monto = licitacion.get("monto_estimado")
    if not monto or monto <= 0:
        return {"error": "No hay monto estimado para análisis económico"}
    
    # Determinar tipo de obra
    titulo = licitacion.get("titulo", "").lower()
    descripcion = licitacion.get("descripcion", "").lower()
    texto = f"{titulo} {descripcion}"
    
    tipo_obra = "default"
    if any(p in texto for p in ["mejoramiento", "remodelación", "reparación"]):
        tipo_obra = "remodelacion"
    elif any(p in texto for p in ["construcción", "edificación", "obra civil"]):
        tipo_obra = "construccion"
    elif any(p in texto for p in ["eléctrica", "electricidad", "iluminación"]):
        tipo_obra = "electricidad"
    elif any(p in texto for p in ["gas", "gasfitería", "sanitaria"]):
        tipo_obra = "gasfiteria"
    
    costos = COSTOS_ESTIMADOS.get(tipo_obra, COSTOS_ESTIMADOS["default"])
    
    # Calcular costos estimados
    materiales = monto * costos["materiales"]
    mano_obra = monto * costos["mano_obra"]
    administrativo = monto * costos["administrativo"]
    impuestos = monto * costos["impuestos"]
    costo_total = materiales + mano_obra + administrativo + impuestos
    
    # Utilidad
    utilidad = monto - costo_total
    utilidad_porcentaje = utilidad / monto if monto > 0 else 0
    
    # Evaluación
    if utilidad_porcentaje >= UTILIDAD_MIN:
        economia = "🟢 Económicamente viable"
    elif utilidad_porcentaje >= UTILIDAD_MIN * 0.5:
        economia = "🟡 Económicamente ajustado"
    else:
        economia = "🔴 No económicamente viable"
    
    return {
        "tipo_obra": tipo_obra,
        "monto_total": monto,
        "costos": {
            "materiales": materiales,
            "mano_obra": mano_obra,
            "administrativo": administrativo,
            "impuestos": impuestos,
            "total": costo_total
        },
        "utilidad": utilidad,
        "utilidad_porcentaje": utilidad_porcentaje,
        "economia": economia,
        "requiere_reajuste": utilidad_porcentaje < UTILIDAD_MIN
    }

def analisis_viabilidad(licitacion: Dict) -> Dict:
    """Análisis de viabilidad técnica"""
    titulo = licitacion.get("titulo", "")
    descripcion = licitacion.get("descripcion", "")
    texto = f"{titulo} {descripcion}".lower()
    
    # Evaluar complejidad
    palabras_alta = ["complejo", "gran", "especializado", "técnico", "certificación", "norma"]
    palabras_media = ["estándar", "convencional", "regular", "típico"]
    
    complejidad = "media"
    if any(p in texto for p in palabras_alta):
        complejidad = "alta"
    elif all(p not in texto for p in palabras_alta + palabras_media):
        complejidad = "baja"
    
    # Plazos (si están disponibles)
    fecha_cierre = licitacion.get("fecha_cierre")
    plazo_adecuado = None
    if fecha_cierre:
        try:
            if isinstance(fecha_cierre, str):
                fecha_cierre = datetime.strptime(fecha_cierre, "%Y-%m-%d")
            dias = (fecha_cierre - datetime.now()).days
            plazo_adecuado = dias > 15
        except:
            plazo_adecuado = None
    
    # Riesgos técnicos
    riesgos = []
    if complejidad == "alta":
        riesgos.append("⚠️ Alta complejidad técnica")
    if plazo_adecuado is False:
        riesgos.append("⚠️ Plazo ajustado para preparación")
    if not licitacion.get("descripcion"):
        riesgos.append("⚠️ Descripción incompleta de alcances")
    
    return {
        "complejidad": complejidad,
        "plazo_adecuado": plazo_adecuado,
        "riesgos_tecnicos": riesgos,
        "viabilidad": "🟢 Viable" if complejidad != "alta" else "🟡 Requiere evaluación"
    }

def analisis_pagos(organismo: str) -> Dict:
    """Análisis de historial de pagos"""
    historial = obtener_historial_pagos(organismo)
    
    if historial["total"] == 0:
        return {
            "pago_estimado": "❓ Sin historial - Riesgo desconocido",
            "recomendacion": "⚠️ Investigar historial del organismo",
            "score": 50
        }
    
    if historial["promedio_mora"] <= DIAS_PAGO_IDEAL:
        return {
            "pago_estimado": f"✅ {historial['promedio_mora']:.0f} días (Excelente)",
            "recomendacion": "✅ Organismo confiable para pago a tiempo",
            "score": 100
        }
    elif historial["promedio_mora"] <= DIAS_PAGO_MAXIMO:
        return {
            "pago_estimado": f"🟡 {historial['promedio_mora']:.0f} días (Regular)",
            "recomendacion": "⚠️ Considerar financiamiento propio",
            "score": 70
        }
    else:
        return {
            "pago_estimado": f"🔴 {historial['promedio_mora']:.0f} días (Moroso)",
            "recomendacion": "🔴 Alto riesgo de mora - Solicitar garantías",
            "score": 30
        }

def analisis_competitivo(licitacion: Dict) -> Dict:
    """Estrategia de oferta competitiva"""
    monto = licitacion.get("monto_estimado")
    if not monto:
        return {"error": "Sin monto para análisis competitivo"}
    
    # Recomendación de precio
    precio_ganador = monto * 0.92  # 8% menos para ser competitivo
    utilidad_proyectada = monto - (monto * 0.92)
    utilidad_porcentaje = utilidad_proyectada / monto if monto > 0 else 0
    
    return {
        "precio_referencia": monto,
        "precio_sugerido": precio_ganador,
        "descuento_sugerido": 0.08,
        "utilidad_proyectada": utilidad_proyectada,
        "utilidad_porcentaje": utilidad_porcentaje,
        "recomendacion": "✅ Competitivo" if utilidad_porcentaje >= UTILIDAD_MIN else "⚠️ Ajustar estrategia"
    }

def generar_reporte_completo(licitacion_id: int) -> Dict:
    """Genera reporte completo de análisis"""
    licitacion = obtener_licitacion(licitacion_id)
    if not licitacion:
        return {"error": f"No se encontró licitación {licitacion_id}"}
    
    organismo = licitacion.get("organismo", "")
    
    # Ejecutar análisis
    economico = analisis_economico(licitacion)
    viabilidad = analisis_viabilidad(licitacion)
    pagos = analisis_pagos(organismo)
    competitivo = analisis_competitivo(licitacion)
    
    # Puntaje total
    puntaje = 0
    if economico.get("utilidad_porcentaje", 0) >= UTILIDAD_MIN:
        puntaje += 30
    elif economico.get("utilidad_porcentaje", 0) >= UTILIDAD_MIN * 0.5:
        puntaje += 15
    
    if pagos.get("score", 0) >= 70:
        puntaje += 30
    elif pagos.get("score", 0) >= 50:
        puntaje += 15
    
    if viabilidad.get("complejidad") != "alta":
        puntaje += 20
    else:
        puntaje += 10
    
    if competitivo.get("utilidad_porcentaje", 0) >= UTILIDAD_MIN:
        puntaje += 20
    else:
        puntaje += 10
    
    return {
        "licitacion": licitacion,
        "analisis_economico": economico,
        "analisis_viabilidad": viabilidad,
        "analisis_pagos": pagos,
        "analisis_competitivo": competitivo,
        "puntaje_total": puntaje,
        "recomendacion_final": "🟢 RECOMENDADA" if puntaje >= 70 else "🟡 EVALUAR" if puntaje >= 50 else "🔴 NO RECOMENDADA",
        "fecha_analisis": datetime.now().isoformat()
    }

def imprimir_reporte(reporte: Dict):
    """Imprime reporte en formato legible"""
    if "error" in reporte:
        print(f"❌ {reporte['error']}")
        return
    
    lic = reporte["licitacion"]
    
    print("\n" + "=" * 80)
    print(f"📋 ANÁLISIS PROFUNDO - {lic.get('codigo_licitacion', 'N/A')}")
    print("=" * 80)
    print(f"📌 {lic.get('titulo', 'Sin título')}")
    print(f"🏛️ {lic.get('organismo', 'No especificado')}")
    print(f"💰 {formatear_monto(lic.get('monto_estimado'))}")
    print(f"📅 Publicación: {lic.get('fecha_publicacion', 'N/A')} | Cierre: {lic.get('fecha_cierre', 'N/A')}")
    print("=" * 80)
    
    # Económico
    eco = reporte["analisis_economico"]
    print("\n📊 ANÁLISIS ECONÓMICO:")
    if "error" in eco:
        print(f"   {eco['error']}")
    else:
        print(f"   Tipo obra: {eco.get('tipo_obra', 'N/A')}")
        print(f"   Utilidad estimada: {formatear_monto(eco.get('utilidad', 0))} ({eco.get('utilidad_porcentaje', 0)*100:.1f}%)")
        print(f"   {eco.get('economia', 'N/A')}")
    
    # Viabilidad
    via = reporte["analisis_viabilidad"]
    print(f"\n🔧 VIABILIDAD TÉCNICA:")
    print(f"   Complejidad: {via.get('complejidad', 'N/A')}")
    print(f"   {via.get('viabilidad', 'N/A')}")
    for riesgo in via.get("riesgos_tecnicos", []):
        print(f"   {riesgo}")
    
    # Pagos
    pag = reporte["analisis_pagos"]
    print(f"\n💳 ANÁLISIS DE PAGOS:")
    print(f"   {pag.get('pago_estimado', 'N/A')}")
    print(f"   {pag.get('recomendacion', 'N/A')}")
    
    # Competitivo
    comp = reporte["analisis_competitivo"]
    if "error" not in comp:
        print(f"\n🎯 ESTRATEGIA DE OFERTA:")
        print(f"   Precio referencia: {formatear_monto(comp.get('precio_referencia', 0))}")
        print(f"   Precio sugerido: {formatear_monto(comp.get('precio_sugerido', 0))}")
        print(f"   Utilidad proyectada: {formatear_monto(comp.get('utilidad_proyectada', 0))} ({comp.get('utilidad_porcentaje', 0)*100:.1f}%)")
        print(f"   {comp.get('recomendacion', 'N/A')}")
    
    # Resumen
    print("\n" + "=" * 80)
    print(f"📊 PUNTAJE TOTAL: {reporte.get('puntaje_total', 0)}/100")
    print(f"🏆 RECOMENDACIÓN: {reporte.get('recomendacion_final', 'N/A')}")
    print("=" * 80)

def main():
    parser = argparse.ArgumentParser(description="Análisis profundo de licitaciones")
    parser.add_argument("--licitacion", type=int, required=True, help="ID de la licitación")
    parser.add_argument("--guardar", action="store_true", help="Guardar en Supabase")
    args = parser.parse_args()
    
    print(f"🔍 Analizando licitación {args.licitacion}...")
    reporte = generar_reporte_completo(args.licitacion)
    imprimir_reporte(reporte)
    
    if args.guardar:
        try:
            db = DatabaseManager().get_service_client()
            db.table("analisis_licitaciones").insert({
                "licitacion_id": args.licitacion,
                "riesgo_legal": "Bajo" if reporte.get("puntaje_total", 0) >= 70 else "Medio",
                "foda": reporte.get("licitacion", {}),
                "puntaje_total": reporte.get("puntaje_total", 0)
            }).execute()
            print("\n✅ Análisis guardado en Supabase")
        except Exception as e:
            print(f"\n⚠️ Error al guardar: {e}")

if __name__ == "__main__":
    main()
