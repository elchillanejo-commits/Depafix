#!/usr/bin/env python3
"""Carta Conductora. Se genera fresca y lista dinámicamente los documentos incluidos."""
from datetime import date
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import cm

import comun

_MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
          "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def generar(cfg, documentos_incluidos, salida):
    destino = salida / f"Carta_{cfg['codigo_sence']}.pdf"
    cv = canvas.Canvas(str(destino), pagesize=letter)
    W, H = letter
    y = H - 3 * cm
    cv.setFont("Helvetica", 10)

    h = date.today()
    cv.drawRightString(W - 3 * cm, y,
                       f"{cfg.get('ciudad', 'Punta Arenas')}, {h.day} de {_MESES[h.month-1]} de {h.year}")
    y -= 1.5 * cm
    for ln in ["Señores", "Dirección Regional SENCE", "Presente"]:
        cv.drawString(3 * cm, y, ln); y -= 0.6 * cm
    y -= 0.8 * cm
    cv.drawString(3 * cm, y, f"Ref.: Ingreso curso código {cfg['codigo_sence']} — {cfg['nombre_curso']}")
    y -= 1.2 * cm
    cv.drawString(3 * cm, y, "Junto con saludar, se remiten los siguientes documentos:")
    y -= 1 * cm
    for i, doc in enumerate(documentos_incluidos, 1):    # lista lo realmente generado
        cv.drawString(3.5 * cm, y, f"{i}. {doc}"); y -= 0.6 * cm
    y -= 1.5 * cm
    cv.drawString(3 * cm, y, "Saluda atentamente,")
    y -= 2 * cm
    cv.drawString(3 * cm, y, "_______________________________")
    cv.drawString(3 * cm, y - 0.6 * cm, cfg["representante"])
    cv.drawString(3 * cm, y - 1.2 * cm,
                  f"{cfg['otec_razon_social']} — RUT {comun.normalizar_rut(cfg['otec_rut'])}")
    cv.save()
    return destino
