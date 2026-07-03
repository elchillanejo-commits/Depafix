#!/usr/bin/env python3
"""Núcleo compartido: config, RUT, overlay, detección de archivos, Regla de Oro."""
import json
import sys
from decimal import Decimal
from pathlib import Path
from io import BytesIO

from reportlab.pdfgen import canvas
from pypdf import PdfReader, PdfWriter

BASE = Path(__file__).resolve().parent          # path anchoring, no cwd
CONFIG = BASE / "config_curso.json"
SALIDA = BASE / "salida"
SALIDA.mkdir(exist_ok=True)                      # Regla de Oro

REQUERIDOS = ["codigo_sence", "nombre_curso", "otec_razon_social",
              "otec_rut", "representante", "fecha_inicio", "fecha_termino"]


def cargar_config(interactivo=True):
    cfg = json.loads(CONFIG.read_text(encoding="utf-8")) if CONFIG.exists() else {}
    faltan = [k for k in REQUERIDOS if not cfg.get(k)]
    if faltan and interactivo:
        print(f"Faltan {len(faltan)} datos del curso:")
        for k in faltan:
            cfg[k] = pedir(k)
        CONFIG.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Config actualizada → {CONFIG.name}")
    elif faltan:
        sys.exit(f"Faltan datos y modo interactivo off: {faltan}")
    return cfg


def pedir(campo, default=None):
    etiqueta = campo.replace("_", " ")
    val = input(f"  {etiqueta}{f' [{default}]' if default else ''}: ").strip()
    return val or default or ""


def normalizar_rut(rut):
    r = str(rut).replace(".", "").replace("-", "").replace(" ", "").upper()
    return f"{r[:-1]}-{r[-1]}" if len(r) >= 2 else rut   # 123456789 → 12345678-9, K mayúscula


def fmt_clp(valor):
    return f"${Decimal(str(valor)):,.0f}".replace(",", ".")   # Decimal, nunca float


def detectar_archivos(carpeta):
    """Auto-detecta insumos por keyword. Devuelve {tipo: Path}."""
    carpeta = Path(carpeta)
    if not carpeta.exists():
        carpeta.mkdir(parents=True, exist_ok=True)          # Regla de Oro
        return {}
    patrones = {
        "plantilla_dj":       ["dj", "declaracion", "jurada"],
        "plantilla_contrato": ["contrato"],
        "plantilla_carta":    ["carta", "conductora"],
        "alumnos":            ["alumnos", "nomina", "estudiantes"],
        "logo":               ["logo"],
    }
    encontrados = {}
    for p in sorted(carpeta.iterdir()):
        nombre = p.name.lower()
        for tipo, claves in patrones.items():
            if any(c in nombre for c in claves):
                encontrados.setdefault(tipo, p)              # primera coincidencia gana
    return encontrados


def overlay(plantilla, campos, destino):
    """Estampa `campos` [{pagina,x,top,texto,size}] sobre plantilla PDF.
    `top` = estilo pdfplumber (origen arriba) → reportlab: baseline = H - top + 0.22*size."""
    lector = PdfReader(str(plantilla))
    escritor = PdfWriter()
    por_pagina = {}
    for c in campos:
        por_pagina.setdefault(c["pagina"], []).append(c)

    for i, pagina in enumerate(lector.pages):
        if i in por_pagina:
            H = float(pagina.mediabox.height)
            W = float(pagina.mediabox.width)
            buf = BytesIO()
            cv = canvas.Canvas(buf, pagesize=(W, H))
            for c in por_pagina[i]:
                size = c.get("size", 10)
                cv.setFont("Helvetica", size)
                cv.drawString(c["x"], H - c["top"] + 0.22 * size, str(c["texto"]))
            cv.save()
            buf.seek(0)
            pagina.merge_page(PdfReader(buf).pages[0])
        escritor.add_page(pagina)

    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)        # Regla de Oro
    with open(destino, "wb") as f:
        escritor.write(f)
    return destino
