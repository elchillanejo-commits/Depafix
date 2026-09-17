#!/usr/bin/env python3
"""
ANÁLISIS QUIRÚRGICO DE LICITACIÓN (VERSIÓN INTEGRADA)
Extrae bases, analiza PDFs, costea con precios reales y evalúa viabilidad.
"""

import argparse
import sys
import json
import re
import requests
from datetime import datetime
from typing import Dict, List, Optional
from tabulate import tabulate
from bs4 import BeautifulSoup
import pdfplumber
from io import BytesIO

sys.path.insert(0, '/home/ibar/Proyectos/DepaFix')
from core.db_manager import DatabaseManager

# ------------------------------------------------------------
# CONFIGURACIÓN
# ------------------------------------------------------------
API_KEY = "9196E835-EE53-4335-B548-716FBA4BD639"
API_BASE = "https://api.mercadopublico.cl/servicios/v1/publico"
COSTOS_EMPRESA = {
    "materiales": 0.40,
    "mano_obra": 0.30,
    "subcontratos": 0.10,
    "gastos_generales": 0.08,
    "impuestos": 0.05,
    "utilidad_deseada": 0.25
}
UTILIDAD_MIN = 0.25
DIAS_PAGO_IDEAL = 30
DIAS_PAGO_MAXIMO = 45

# ------------------------------------------------------------
# FUNCIONES AUXILIARES
# ------------------------------------------------------------
def formatear_monto(valor):
    if valor is None: return "N/A"
    try: return f"${float(valor):,.0f}"
    except: return "N/A"

def obtener_licitacion(id_licitacion: int) -> Dict:
    db = DatabaseManager().get_service_client()
    result = db.table("licitaciones").select("*").eq("id", id_licitacion).execute()
    return result.data[0] if result.data else None

def obtener_historial_pagos(organismo: str) -> Dict:
    db = DatabaseManager().get_service_client()
    result = db.table("historial_pagos").select("*").ilike("organismo", f"%{organismo}%").execute()
    if not result.data:
        return {"total": 0, "promedio_mora": None, "clasificacion": "❓ Sin historial"}
    moras = [r.get("dias_mora", 0) for r in result.data if r.get("dias_mora")]
    promedio = sum(moras) / len(moras) if moras else 0
    if promedio <= DIAS_PAGO_IDEAL:
        clasificacion = "🟢 Excelente pagador"
    elif promedio <= DIAS_PAGO_MAXIMO:
        clasificacion = "🟡 Pagador regular"
    else:
        clasificacion = "🔴 Mal pagador"
    return {"total": len(result.data), "promedio_mora": promedio, "clasificacion": clasificacion}

def obtener_precios_referencia() -> Dict:
    db = DatabaseManager().get_service_client()
    result = db.table("precios_referencia").select("*").execute()
    return {r["producto"]: r["precio_promedio"] for r in result.data}

def extraer_documentos(codigo: str) -> List[Dict]:
    """Scraping de documentos desde el portal de Mercado Público"""
    url = f"https://www.mercadopublico.cl/Procurement/Modules/RFB/DetailsAcquisition.aspx?id={codigo}"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.content, "html.parser")
        docs = []
        for a in soup.find_all("a", href=re.compile(r"\.pdf", re.I)):
            href = a.get("href")
            texto = a.text.strip()
            if href:
                if not href.startswith("http"):
                    href = "https://www.mercadopublico.cl" + href
                docs.append({"nombre": texto or "Documento", "url": href})
        return docs
    except Exception as e:
        print(f"⚠️ No se pudieron extraer documentos: {e}")
        return []

def descargar_y_analizar_pdf(url: str) -> Dict:
    """Descarga un PDF y extrae condiciones clave"""
    try:
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=60)
        resp.raise_for_status()
        with pdfplumber.open(BytesIO(resp.content)) as pdf:
            texto = "".join(pagina.extract_text() or "" for pagina in pdf.pages)
        resultado = {
            "plazo_ejecucion": None,
            "plazo_pago_dias": None,
            "garantias": None,
            "penalizaciones": None,
            "requisitos_tecnicos": None
        }
        # Buscar plazos
        for pat in [r"plazo\s*(?:de\s*)?ejecución\s*[:]\s*(\d+)\s*(?:días|dias)",
                    r"plazo\s*[:]\s*(\d+)\s*(?:días|dias)",
                    r"(\d+)\s*(?:días|dias)\s*(?:de\s*ejecución)"]:
            m = re.search(pat, texto, re.I)
            if m:
                resultado["plazo_ejecucion"] = int(m.group(1))
                break
        for pat in [r"pago\s*(?:a\s*)?(\d+)\s*(?:días|dias)",
                    r"plazo\s*de\s*pago\s*(\d+)\s*(?:días|dias)",
                    r"(\d+)\s*(?:días|dias)\s*(?:de\s*pago)"]:
            m = re.search(pat, texto, re.I)
            if m:
                resultado["plazo_pago_dias"] = int(m.group(1))
                break
        if re.search(r"boleta\s*de\s*garant", texto, re.I):
            resultado["garantias"] = "Boleta de garantía requerida"
        elif re.search(r"garant", texto, re.I):
            resultado["garantias"] = "Garantía requerida (ver detalles)"
        if re.search(r"penalizaci", texto, re.I):
            resultado["penalizaciones"] = "Cláusulas de penalización detectadas"
        if re.search(r"certificaci|norma", texto, re.I):
            resultado["requisitos_tecnicos"] = "Requisitos técnicos y/o certificaciones mencionados"
        return resultado
    except Exception as e:
        return {"error": f"No se pudo analizar PDF: {e}"}

def calcular_presupuesto_empresa(monto_oficial: float) -> Dict:
    if not monto_oficial or monto_oficial <= 0:
        return {"error": "No hay monto oficial"}
    materiales = monto_oficial * COSTOS_EMPRESA["materiales"]
    mano_obra = monto_oficial * COSTOS_EMPRESA["mano_obra"]
    subcontratos = monto_oficial * COSTOS_EMPRESA["subcontratos"]
    gastos_generales = monto_oficial * COSTOS_EMPRESA["gastos_generales"]
    impuestos = monto_oficial * COSTOS_EMPRESA["impuestos"]
    costo_total = materiales + mano_obra + subcontratos + gastos_generales + impuestos
    utilidad = costo_total * COSTOS_EMPRESA["utilidad_deseada"]
    precio_final = costo_total + utilidad
    margen = (precio_final - monto_oficial) / monto_oficial if monto_oficial > 0 else 0
    return {
        "presupuesto_oficial": monto_oficial,
        "materiales": materiales,
        "mano_obra": mano_obra,
        "subcontratos": subcontratos,
        "gastos_generales": gastos_generales,
        "impuestos": impuestos,
        "costo_total": costo_total,
        "utilidad": utilidad,
        "precio_final": precio_final,
        "margen_porcentaje": margen * 100,
        "es_viable": margen >= 0.0
    }

def analizar_plazos(lic: Dict) -> Dict:
    fecha_cierre = lic.get("fecha_cierre")
    if not fecha_cierre:
        return {"dias_para_cierre": None, "evaluacion": "No disponible"}
    try:
        if isinstance(fecha_cierre, str):
            fecha_cierre_dt = datetime.strptime(fecha_cierre, "%Y-%m-%d")
        else:
            fecha_cierre_dt = fecha_cierre
        dias = (fecha_cierre_dt - datetime.now()).days
        if dias < 7:
            eval_ = "⚠️ Plazo muy corto (<7 días)"
        elif dias < 15:
            eval_ = "⚠️ Plazo ajustado (7-15 días)"
        elif dias < 30:
            eval_ = "✅ Plazo adecuado (15-30 días)"
        else:
            eval_ = "✅ Plazo amplio (>30 días)"
        return {"dias_para_cierre": dias, "evaluacion": eval_}
    except:
        return {"dias_para_cierre": None, "evaluacion": "No disponible"}

def generar_reporte_completo(licitacion_id: int) -> Dict:
    lic = obtener_licitacion(licitacion_id)
    if not lic:
        return {"error": f"No se encontró licitación con ID {licitacion_id}"}
    codigo = lic.get("codigo_licitacion")
    organismo = lic.get("organismo", "")
    monto_oficial = lic.get("monto_estimado")
    
    # 1. Historial de pagos
    historial = obtener_historial_pagos(organismo)
    
    # 2. Presupuesto empresa
    presupuesto = calcular_presupuesto_empresa(monto_oficial)
    
    # 3. Plazos
    plazos = analizar_plazos(lic)
    
    # 4. Documentos (scraping)
    documentos = extraer_documentos(codigo) if codigo else []
    
    # 5. Análisis de PDF (si hay documentos)
    analisis_pdf = None
    if documentos:
        # Tomar el primer PDF encontrado (puede mejorarse)
        for doc in documentos:
            if doc["url"].endswith(".pdf"):
                analisis_pdf = descargar_y_analizar_pdf(doc["url"])
                if analisis_pdf and "error" not in analisis_pdf:
                    break
    
    # 6. Puntaje y viabilidad
    puntaje = 0
    if presupuesto.get("es_viable", False):
        puntaje += 35
    elif presupuesto.get("es_viable") is False:
        puntaje += 10
    else:
        puntaje += 5
    
    if historial["clasificacion"] == "🟢 Excelente pagador":
        puntaje += 35
    elif historial["clasificacion"] == "🟡 Pagador regular":
        puntaje += 20
    elif historial["clasificacion"] == "❓ Sin historial":
        puntaje += 10
    else:
        puntaje += 5
    
    if plazos["dias_para_cierre"] and plazos["dias_para_cierre"] >= 15:
        puntaje += 30
    elif plazos["dias_para_cierre"] and plazos["dias_para_cierre"] >= 7:
        puntaje += 15
    else:
        puntaje += 5
    
    return {
        "licitacion": lic,
        "historial_pagos": historial,
        "presupuesto_empresa": presupuesto,
        "plazos": plazos,
        "documentos": documentos[:5],
        "analisis_pdf": analisis_pdf,
        "puntaje_total": min(puntaje, 100),
        "recomendacion": "🟢 RECOMENDADA" if puntaje >= 70 else "🟡 EVALUAR" if puntaje >= 50 else "🔴 NO RECOMENDADA"
    }

def imprimir_reporte(reporte: Dict):
    if "error" in reporte:
        print(f"❌ {reporte['error']}")
        return
    lic = reporte["licitacion"]
    pres = reporte["presupuesto_empresa"]
    hist = reporte["historial_pagos"]
    plaz = reporte["plazos"]
    
    print("\n" + "=" * 90)
    print(f"🔬 ANÁLISIS QUIRÚRGICO - {lic.get('codigo_licitacion', 'N/A')}")
    print("=" * 90)
    print(f"📌 {lic.get('titulo', 'Sin título')}")
    print(f"🏛️ {lic.get('organismo', 'No especificado')}")
    print(f"💰 Presupuesto oficial: {formatear_monto(lic.get('monto_estimado'))}")
    print(f"📅 Publicación: {lic.get('fecha_publicacion', 'N/A')} | Cierre: {lic.get('fecha_cierre', 'N/A')}")
    print("-" * 90)
    
    # Presupuesto empresa
    print("\n📊 PRESUPUESTO EMPRESA")
    if "error" in pres:
        print(f"❌ {pres['error']}")
    else:
        tabla = [
            ["Concepto", "Monto", "% del oficial"],
            ["Materiales", formatear_monto(pres["materiales"]), f"{pres['materiales']/pres['presupuesto_oficial']*100:.1f}%"],
            ["Mano de obra", formatear_monto(pres["mano_obra"]), f"{pres['mano_obra']/pres['presupuesto_oficial']*100:.1f}%"],
            ["Subcontratos", formatear_monto(pres["subcontratos"]), f"{pres['subcontratos']/pres['presupuesto_oficial']*100:.1f}%"],
            ["Gastos generales", formatear_monto(pres["gastos_generales"]), f"{pres['gastos_generales']/pres['presupuesto_oficial']*100:.1f}%"],
            ["Impuestos", formatear_monto(pres["impuestos"]), f"{pres['impuestos']/pres['presupuesto_oficial']*100:.1f}%"],
            ["-"*30, "", ""],
            ["Costo total", formatear_monto(pres["costo_total"]), f"{pres['costo_total']/pres['presupuesto_oficial']*100:.1f}%"],
            ["Utilidad (25%)", formatear_monto(pres["utilidad"]), f"{pres['utilidad']/pres['presupuesto_oficial']*100:.1f}%"],
            ["-"*30, "", ""],
            ["PRECIO FINAL", formatear_monto(pres["precio_final"]), f"{pres['precio_final']/pres['presupuesto_oficial']*100:.1f}%"],
        ]
        print(tabulate(tabla, headers="firstrow", tablefmt="grid"))
        print(f"\n📊 Margen vs oficial: {pres['margen_porcentaje']:.1f}%")
        print(f"✅ {'VIABLE' if pres['es_viable'] else 'NO VIABLE (requiere ajuste)'}")
    
    # Historial de pagos
    print("\n💳 HISTORIAL DE PAGOS")
    print(f"   Registros: {hist['total']}")
    if hist['promedio_mora'] is not None:
        print(f"   Mora promedio: {hist['promedio_mora']:.0f} días")
    print(f"   Clasificación: {hist['clasificacion']}")
    
    # Plazos
    print("\n⏰ PLAZOS")
    print(f"   Días para cierre: {plaz['dias_para_cierre'] if plaz['dias_para_cierre'] is not None else 'N/A'}")
    print(f"   Evaluación: {plaz['evaluacion']}")
    
    # Documentos
    if reporte.get("documentos"):
        print("\n📄 DOCUMENTOS ENCONTRADOS")
        for d in reporte["documentos"][:3]:
            print(f"   - {d['nombre']}: {d['url'][:60]}...")
    
    # Análisis PDF
    if reporte.get("analisis_pdf") and "error" not in reporte["analisis_pdf"]:
        pdf = reporte["analisis_pdf"]
        print("\n📋 ANÁLISIS DE BASES (desde PDF)")
        if pdf.get("plazo_ejecucion"):
            print(f"   Plazo de ejecución: {pdf['plazo_ejecucion']} días")
        if pdf.get("plazo_pago_dias"):
            print(f"   Plazo de pago: {pdf['plazo_pago_dias']} días")
        if pdf.get("garantias"):
            print(f"   Garantías: {pdf['garantias']}")
        if pdf.get("penalizaciones"):
            print(f"   Penalizaciones: {pdf['penalizaciones']}")
        if pdf.get("requisitos_tecnicos"):
            print(f"   Requisitos: {pdf['requisitos_tecnicos']}")
    
    # Resumen
    print("\n" + "=" * 90)
    print(f"📊 PUNTAJE TOTAL: {reporte['puntaje_total']}/100")
    print(f"🏆 RECOMENDACIÓN: {reporte['recomendacion']}")
    print("=" * 90)

def main():
    parser = argparse.ArgumentParser(description="Análisis quirúrgico completo de licitación")
    parser.add_argument("--licitacion", type=int, required=True, help="ID de la licitación en Supabase")
    parser.add_argument("--guardar", action="store_true", help="Guardar análisis en Supabase")
    args = parser.parse_args()
    
    print(f"🔬 Analizando licitación ID {args.licitacion}...")
    reporte = generar_reporte_completo(args.licitacion)
    imprimir_reporte(reporte)
    
    if args.guardar and "error" not in reporte:
        db = DatabaseManager().get_service_client()
        db.table("analisis_licitaciones").insert({
            "licitacion_id": args.licitacion,
            "riesgo_legal": "Bajo" if reporte["puntaje_total"] >= 70 else "Medio",
            "puntaje_total": reporte["puntaje_total"],
            "foda": reporte
        }).execute()
        print("\n✅ Análisis quirúrgico guardado en Supabase")

if __name__ == "__main__":
    main()
