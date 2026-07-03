#!/usr/bin/env python3
"""Declaración Jurada. Estampa sobre plantilla; si no hay, la genera (Regla de Oro)."""
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import cm

import comun


def generar(cfg, archivos, salida):
    plantilla = archivos.get("plantilla_dj")
    mapeo = cfg.get("mapeo_dj", [])
    destino = salida / f"DJ_{cfg['codigo_sence']}.pdf"
    if plantilla and mapeo:
        campos = [{**m, "texto": _valor(m["clave"], cfg)} for m in mapeo]
        return comun.overlay(plantilla, campos, destino)
    return _desde_cero(cfg, destino)               # sin plantilla → genera básica


def _valor(clave, cfg):
    return comun.normalizar_rut(cfg["otec_rut"]) if clave == "otec_rut" else cfg.get(clave, "")


def _desde_cero(cfg, destino):
    cv = canvas.Canvas(str(destino), pagesize=letter)
    W, H = letter
    y = H - 3 * cm
    cv.setFont("Helvetica-Bold", 13)
    cv.drawCentredString(W / 2, y, "DECLARACIÓN JURADA SIMPLE")
    cv.setFont("Helvetica", 10)
    y -= 1.5 * cm
    lineas = [
        f"OTEC: {cfg['otec_razon_social']}  RUT: {comun.normalizar_rut(cfg['otec_rut'])}",
        f"Representante legal: {cfg['representante']}",
        f"Curso: {cfg['nombre_curso']}  (Código SENCE {cfg['codigo_sence']})",
        f"Período: {cfg['fecha_inicio']} al {cfg['fecha_termino']}",
        "",
        "Declara bajo juramento que los antecedentes presentados para el ingreso",
        "del curso son fidedignos y se ajustan a la normativa SENCE vigente.",
    ]
    for ln in lineas:
        cv.drawString(3 * cm, y, ln); y -= 0.7 * cm
    y -= 2 * cm
    cv.drawString(3 * cm, y, "_______________________________")
    cv.drawString(3 * cm, y - 0.6 * cm, cfg["representante"])
    cv.save()
    return destino
