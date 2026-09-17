#!/usr/bin/env python3
"""
Analiza PDFs de bases y extrae condiciones clave
"""

import sys
import re
import requests
import pdfplumber
from io import BytesIO
sys.path.insert(0, '/home/ibar/Proyectos/DepaFix')

def descargar_pdf(url: str) -> bytes:
    """Descarga un PDF desde una URL"""
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        resp = requests.get(url, headers=headers, timeout=60)
        resp.raise_for_status()
        return resp.content
    except Exception as e:
        print(f"❌ Error al descargar PDF: {e}", file=sys.stderr)
        return None

def extraer_texto_pdf(contenido: bytes) -> str:
    """Extrae texto de un PDF desde bytes"""
    try:
        with pdfplumber.open(BytesIO(contenido)) as pdf:
            texto = ""
            for pagina in pdf.pages:
                pagina_texto = pagina.extract_text() or ""
                texto += pagina_texto
        return texto
    except Exception as e:
        print(f"❌ Error al leer PDF: {e}", file=sys.stderr)
        return ""

def analizar_bases(texto: str) -> dict:
    """Analiza el texto buscando condiciones clave"""
    resultado = {
        "plazo_ejecucion": None,
        "garantias": None,
        "forma_pago": None,
        "penalizaciones": None,
        "requisitos_tecnicos": None,
        "plazo_pago_dias": None
    }
    
    # Buscar plazos de ejecución
    patrones_plazo = [
        r"plazo\s*(?:de\s*)?ejecución\s*[:]\s*(\d+)\s*(?:días|dias)",
        r"plazo\s*[:]\s*(\d+)\s*(?:días|dias)",
        r"(\d+)\s*(?:días|dias)\s*(?:de\s*ejecución)",
    ]
    for pat in patrones_plazo:
        match = re.search(pat, texto, re.IGNORECASE)
        if match:
            resultado["plazo_ejecucion"] = int(match.group(1))
            break
    
    # Buscar plazos de pago
    patrones_pago = [
        r"pago\s*(?:a\s*)?(\d+)\s*(?:días|dias)",
        r"plazo\s*de\s*pago\s*(\d+)\s*(?:días|dias)",
        r"(\d+)\s*(?:días|dias)\s*(?:de\s*pago)"
    ]
    for pat in patrones_pago:
        match = re.search(pat, texto, re.IGNORECASE)
        if match:
            resultado["plazo_pago_dias"] = int(match.group(1))
            resultado["forma_pago"] = f"{match.group(1)} días"
            break
    
    # Garantías
    if re.search(r"boleta\s*de\s*garant", texto, re.IGNORECASE):
        resultado["garantias"] = "Boleta de garantía requerida"
    elif re.search(r"garant", texto, re.IGNORECASE):
        resultado["garantias"] = "Garantía requerida (verificar detalles)"
    
    # Penalizaciones
    if re.search(r"penalizaci", texto, re.IGNORECASE):
        resultado["penalizaciones"] = "Cláusulas de penalización detectadas"
    
    # Requisitos técnicos
    if re.search(r"certificaci", texto, re.IGNORECASE) or re.search(r"norma", texto, re.IGNORECASE):
        resultado["requisitos_tecnicos"] = "Requisitos técnicos y/o certificaciones mencionados"
    
    return resultado

def main():
    import argparse
    import json
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", type=str, required=True, help="URL del PDF")
    parser.add_argument("--guardar", action="store_true", help="Guardar análisis")
    args = parser.parse_args()
    
    print(f"📥 Descargando PDF...")
    contenido = descargar_pdf(args.url)
    if not contenido:
        sys.exit(1)
    
    print(f"📄 Extrayendo texto...")
    texto = extraer_texto_pdf(contenido)
    if not texto:
        print("⚠️ No se pudo extraer texto del PDF")
        sys.exit(1)
    
    print(f"🔍 Analizando bases...")
    analisis = analizar_bases(texto)
    print(json.dumps(analisis, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
