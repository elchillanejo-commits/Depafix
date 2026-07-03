#!/usr/bin/env python3
import urllib.request
import re
import json
import os

def buscar_en_sence():
    print("🔍 Buscando fuentes oficiales en SENCE...")
    url_base = "https://www.sence.gob.cl/personas/normativa-y-manuales"
    try:
        req = urllib.request.Request(url_base, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as response:
            html = response.read().decode("utf-8")
        
        # Buscar enlaces a PDFs de manuales o declaraciones juradas
        links = re.findall(r'href="([^"]+\.pdf)"', html)
        print(f"📊 Se encontraron {len(links)} documentos PDF en la pagina de normativa.")
        
        # Filtrar los mas relevantes para el ingreso
        palabras_clave = ["manual", "procedimiento", "declaracion", "dj", "formato"]
        encontrados = []
        for l in links:
            link_lower = l.lower()
            if any(k in link_lower for k in palabras_clave):
                full_url = l if l.startswith("http") else f"https://www.sence.gob.cl{l}"
                if full_url not in encontrados:
                    encontrados.append(full_url)
                    
        print("\n📋 Enlaces sugeridos para revisar formatos oficiales:")
        for e in encontrados[:5]:
            print(f"  -> {e}")
            
    except Exception as e:
        print(f"❌ No se pudo conectar a la web de SENCE: {e}")
        print("💡 Consejo: Descarga los formatos DJ y Carta desde tu portal SENCE Empresa e inyectalos al script.")

if __name__ == "__main__":
    buscar_en_sence()
