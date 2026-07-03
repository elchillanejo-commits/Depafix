#!/usr/bin/env python3
import os
from pypdf import PdfReader

def extraer_texto_legal():
    pdf_path = "./documentos_sence/Manual_Procedimientos_SENCE.pdf"
    if not os.path.exists(pdf_path):
        print("❌ El manual descargado no se encuentra en la ruta esperada.")
        return
    
    print("📖 Abriendo manual oficial en disco...")
    reader = PdfReader(pdf_path)
    palabras_clave = ["declaracion jurada", "carta conductora", "contrato de capacitacion"]
    
    for idx, page in enumerate(reader.pages):
        texto = page.extract_text()
        texto_lower = texto.lower()
        if any(keyword in texto_lower for keyword in palabras_clave):
            print(f"\n=== COINCIDENCIA ENCONTRADA EN PAGINA {idx + 1} ===")
            print(texto[:1000])
            print("-" * 40)

if __name__ == "__main__":
    extraer_texto_legal()
