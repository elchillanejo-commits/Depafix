#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
extraer_cotizaciones.py — Extrae texto de cotizaciones reales de PPTOS.

Recorre /home/ibar/Documentos/Conocimiento/Tierra_Construccion/Cotizaciones_Reales/,
lee PDFs (pdfplumber), Excels (pandas) y Words (python-docx),
extrae el texto y lo guarda en cotizaciones_extraidas.txt.
"""
import sys
from pathlib import Path

import pdfplumber
import pandas as pd

try:
    import docx
except ImportError:
    docx = None

CARPETA = Path("/home/ibar/Documentos/Conocimiento/Tierra_Construccion/Cotizaciones_Reales")
SALIDA = Path("cotizaciones_extraidas.txt")


def extraer_pdf(ruta):
    partes = []
    try:
        with pdfplumber.open(ruta) as pdf:
            for pagina in pdf.pages:
                texto = pagina.extract_text()
                if texto:
                    partes.append(texto)
    except Exception as e:
        print(f"  ⚠️ Error leyendo PDF {ruta.name}: {e}")
    return "\n".join(partes)


def extraer_excel(ruta):
    partes = []
    try:
        xl = pd.ExcelFile(ruta)
        for hoja in xl.sheet_names:
            df = xl.parse(hoja)
            partes.append(f"### HOJA: {hoja}\n{df.to_csv(index=False)}")
    except Exception as e:
        print(f"  ⚠️ Error leyendo Excel {ruta.name}: {e}")
    return "\n".join(partes)


def extraer_docx(ruta):
    if docx is None:
        print(f"  ⚠️ python-docx no instalado, saltando {ruta.name}")
        return ""
    partes = []
    try:
        d = docx.Document(ruta)
        for p in d.paragraphs:
            if p.text.strip():
                partes.append(p.text)
        for tabla in d.tables:
            for fila in tabla.rows:
                celdas = [celda.text.strip() for celda in fila.cells]
                partes.append(" | ".join(celdas))
    except Exception as e:
        print(f"  ⚠️ Error leyendo DOCX {ruta.name}: {e}")
    return "\n".join(partes)


def extraer_texto(ruta):
    sufijo = ruta.suffix.lower()
    if sufijo == ".pdf":
        return extraer_pdf(ruta)
    if sufijo in (".xlsx", ".xls", ".xlsm"):
        return extraer_excel(ruta)
    if sufijo == ".docx":
        return extraer_docx(ruta)
    if sufijo in (".txt", ".md"):
        try:
            return ruta.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            print(f"  ⚠️ Error leyendo texto {ruta.name}: {e}")
            return ""
    return ""


def main():
    if not CARPETA.exists():
        print(f"[ERROR] No existe la carpeta: {CARPETA}")
        sys.exit(1)

    archivos = sorted(
        p for p in CARPETA.rglob("*")
        if p.is_file() and p.suffix.lower() in {".pdf", ".xlsx", ".xls", ".xlsm", ".docx", ".txt", ".md"}
    )

    if not archivos:
        print(f"[WARN] No se encontraron archivos en {CARPETA}")
        sys.exit(0)

    print(f"📁 {len(archivos)} archivo(s) encontrado(s) en {CARPETA}")

    bloques = []
    for ruta in archivos:
        print(f"  📄 {ruta.name}")
        texto = extraer_texto(ruta)
        if not texto.strip():
            print(f"    ⚠️ Sin texto extraíble")
            continue
        bloques.append(
            f"===== ARCHIVO: {ruta.name} =====\n"
            f"{texto.strip()}\n"
        )

    SALIDA.write_text("\n".join(bloques), encoding="utf-8")
    print(f"\n✅ Guardado en {SALIDA.resolve()}")
    print(f"   Archivos procesados: {len(archivos)}")


if __name__ == "__main__":
    main()
