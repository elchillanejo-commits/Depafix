#!/usr/bin/env python3
"""Contratos: uno por alumno. Nómina desde config, archivo detectado o interactivo."""
import csv
import json
from pathlib import Path
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import cm
from pypdf import PdfWriter, PdfReader

import comun


def generar(cfg, archivos, salida):
    alumnos = _cargar_alumnos(cfg, archivos)
    if not alumnos:
        print("  Sin nómina. Ingreso interactivo (RUT vacío para terminar):")
        alumnos = _interactivo()

    individuales = []
    plantilla = archivos.get("plantilla_contrato")
    mapeo = cfg.get("mapeo_contrato", [])
    for al in alumnos:
        destino = salida / f"Contrato_{comun.normalizar_rut(al['rut'])}.pdf"
        if plantilla and mapeo:
            campos = [{**m, "texto": _valor(m["clave"], cfg, al)} for m in mapeo]
            comun.overlay(plantilla, campos, destino)
        else:
            _desde_cero(cfg, al, destino)
        individuales.append(destino)

    consolidado = salida / f"Contratos_{cfg['codigo_sence']}.pdf"
    escritor = PdfWriter()
    for pdf in individuales:
        for pagina in PdfReader(str(pdf)).pages:
            escritor.add_page(pagina)
    with open(consolidado, "wb") as f:
        escritor.write(f)
    print(f"  {len(individuales)} contratos generados")
    return consolidado


def _cargar_alumnos(cfg, archivos):
    if cfg.get("alumnos"):
        return cfg["alumnos"]
    ruta = archivos.get("alumnos")
    if not ruta:
        return []
    if ruta.suffix.lower() == ".json":
        return json.loads(Path(ruta).read_text(encoding="utf-8"))
    if ruta.suffix.lower() == ".csv":
        with open(ruta, encoding="utf-8") as f:
            return list(csv.DictReader(f))
    return []


def _interactivo():
    alumnos = []
    while True:
        rut = input("  RUT alumno: ").strip()
        if not rut:
            break
        alumnos.append({"rut": rut, "nombre": input("  Nombre: ").strip()})
    return alumnos


def _valor(clave, cfg, al):
    if clave in ("rut", "alumno_rut"):
        return comun.normalizar_rut(al["rut"])
    if clave in ("nombre", "alumno_nombre"):
        return al.get("nombre", "")
    if clave == "otec_rut":
        return comun.normalizar_rut(cfg["otec_rut"])
    return al.get(clave) or cfg.get(clave, "")


def _desde_cero(cfg, al, destino):
    cv = canvas.Canvas(str(destino), pagesize=letter)
    W, H = letter
    y = H - 3 * cm
    cv.setFont("Helvetica-Bold", 12)
    cv.drawCentredString(W / 2, y, "CONTRATO DE CAPACITACIÓN")
    cv.setFont("Helvetica", 10)
    y -= 1.5 * cm
    lineas = [
        f"Entre {cfg['otec_razon_social']}, RUT {comun.normalizar_rut(cfg['otec_rut'])},",
        f"y don(ña) {al.get('nombre','')}, RUT {comun.normalizar_rut(al['rut'])},",
        "se conviene la participación en el curso:",
        f"  {cfg['nombre_curso']} (Código SENCE {cfg['codigo_sence']})",
        f"  Duración: {cfg.get('horas','___')} horas — {cfg['fecha_inicio']} al {cfg['fecha_termino']}",
        f"  Valor: {comun.fmt_clp(cfg.get('valor_curso', 0))}",
    ]
    for ln in lineas:
        cv.drawString(3 * cm, y, ln); y -= 0.7 * cm
    y -= 2 * cm
    cv.drawString(3 * cm, y, "______________________     ______________________")
    cv.drawString(3 * cm, y - 0.6 * cm, "OTEC                                Alumno")
    cv.save()
    return destino
