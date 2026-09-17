#!/usr/bin/env python3
"""
Extractor de bases y documentos de licitaciones desde Mercado Público
Usa scraping del portal para obtener enlaces a PDFs.
"""

import sys
import requests
from bs4 import BeautifulSoup
import re
sys.path.insert(0, '/home/ibar/Proyectos/DepaFix')
from core.db_manager import DatabaseManager

def obtener_documentos_licitacion(codigo: str) -> list:
    """
    Obtiene lista de documentos asociados a una licitación mediante scraping.
    """
    url = f"https://www.mercadopublico.cl/Procurement/Modules/RFB/DetailsAcquisition.aspx?id={codigo}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    documentos = []
    try:
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.content, "html.parser")
        
        # Buscar enlaces a documentos (ajustar selectores según estructura real)
        # Ejemplo: buscar <a> con href que contenga '.pdf' y texto relacionado
        for a in soup.find_all("a", href=re.compile(r"\.pdf", re.I)):
            href = a.get("href")
            texto = a.text.strip()
            if href:
                if not href.startswith("http"):
                    href = "https://www.mercadopublico.cl" + href
                documentos.append({
                    "nombre": texto or "Documento",
                    "url": href,
                    "tipo": "pdf"
                })
        
        # Si no se encontraron PDFs, buscar enlaces a documentos en general
        if not documentos:
            for a in soup.find_all("a", href=re.compile(r"Documentos|Bases|Anexos", re.I)):
                href = a.get("href")
                texto = a.text.strip()
                if href:
                    if not href.startswith("http"):
                        href = "https://www.mercadopublico.cl" + href
                    documentos.append({
                        "nombre": texto or "Documento",
                        "url": href,
                        "tipo": "link"
                    })
        
        # Filtrar duplicados
        vistos = set()
        docs_unicos = []
        for doc in documentos:
            if doc["url"] not in vistos:
                vistos.add(doc["url"])
                docs_unicos.append(doc)
        
        return docs_unicos
        
    except Exception as e:
        print(f"❌ Error al obtener documentos: {e}", file=sys.stderr)
        return []

def guardar_documentos(codigo: str, documentos: list):
    """Guarda los documentos en una tabla (opcional)"""
    # Aquí podrías guardar en Supabase si creas una tabla documentos_licitacion
    pass

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--codigo", type=str, required=True, help="Código de la licitación")
    parser.add_argument("--guardar", action="store_true", help="Guardar en Supabase")
    args = parser.parse_args()
    
    print(f"🔍 Buscando documentos para {args.codigo}...")
    docs = obtener_documentos_licitacion(args.codigo)
    print(f"📄 Documentos encontrados: {len(docs)}")
    for d in docs[:5]:  # Mostrar primeros 5
        print(f"  - {d['nombre']}: {d['url'][:80]}...")

if __name__ == "__main__":
    main()
