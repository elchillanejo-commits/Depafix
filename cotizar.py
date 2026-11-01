#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generador de cotización en PDF con cláusula de validez blindada y precios dinámicos.

Lee la cláusula desde docs/clausula_validez_blindada.md y la inserta en el PDF
antes del bloque de aceptación y firma. Soporta precios dinámicos mediante
códigos de partida (ej. CER-PISO-01) resueltos contra un catálogo.
"""

import json
import os
from datetime import date, datetime
from fpdf import FPDF

CLAUSE_PATH = "docs/clausula_validez_blindada.md"
CATALOG_PATH = "catalogo_precios.json"
FONT_DIR = "/usr/share/fonts/truetype/dejavu"

DIAS_ULTIMA_ACTUALIZACION = 30


def _normalizar_fecha_precio(valor):
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    if not valor:
        return None
    texto = str(valor).strip()[:10]
    for formato in ("%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(texto, formato).date()
        except ValueError:
            continue
    return None


def validar_precio_material(mat):
    fecha = _normalizar_fecha_precio(mat.get("fecha_precio"))
    if not fecha:
        return True
    if (date.today() - fecha).days > DIAS_ULTIMA_ACTUALIZACION:
        sku = mat.get("codigo") or mat.get("sku") or mat.get("nombre") or "S/N"
        print(f"⚠️ ALERTA: El material {sku} tiene precio desactualizado (fecha: {fecha}). Actualiza antes de cotizar.")
        return False
    return True


def cargar_clausula(ruta=CLAUSE_PATH):
    with open(ruta, "r", encoding="utf-8") as f:
        return f.read()


def cargar_catalogo(ruta=CATALOG_PATH):
    """Carga el catálogo de precios desde JSON. Si no existe, usa catálogo embebido."""
    embebido = {
        "materiales_catalogo": {
            "CER-PISO-01": {
                "codigo": "CER-PISO-01",
                "nombre": "Cerámica piso esmaltada primera calidad",
                "unidad": "m2",
                "precio_base_clp": 12000,
                "es_material": True,
                "componente_material": True,
                "proveedor": "Cerámicas del Sur",
            },
            "REV-INT-01": {
                "codigo": "REV-INT-01",
                "nombre": "Revoque fino interior",
                "unidad": "m2",
                "precio_base_clp": 8500,
                "es_material": True,
                "componente_material": True,
                "proveedor": "Materiales Constructores",
            },
            "PNT-LAT-INT-01": {
                "codigo": "PNT-LAT-INT-01",
                "nombre": "Pintura látex interior blanca",
                "unidad": "m2",
                "precio_base_clp": 4500,
                "es_material": True,
                "componente_material": True,
                "proveedor": "Pinturas Todo",
            },
            "MANO-OBRA-POS": {
                "codigo": "MANO-OBRA-POS",
                "nombre": "Mano de obra colocación cerámica",
                "unidad": "m2",
                "precio_base_clp": 7000,
                "es_material": False,
                "componente_material": False,
                "proveedor": "DepaFix",
            },
            "MANO-OBRA-REV": {
                "codigo": "MANO-OBRA-REV",
                "nombre": "Mano de obra revoque fino",
                "unidad": "m2",
                "precio_base_clp": 5500,
                "es_material": False,
                "componente_material": False,
                "proveedor": "DepaFix",
            },
        },
        "partida_receta": {
            "CER-PISO-01": {
                "codigo_partida": "CER-PISO-01",
                "nombre_partida": "Instalación cerámica piso",
                "descripcion": "Suministro e instalación de cerámica de piso esmaltada, incluye material y mano de obra",
                "unidad_medida": "m2",
                "rendimiento": 1.0,
            },
        },
        "partida_receta_detalle": {
            "CER-PISO-01": [
                {"codigo_partida": "CER-PISO-01", "codigo_material": "CER-PISO-01", "cantidad": 1.05, "nota": "5% de descarte por cortes"},
                {"codigo_partida": "CER-PISO-01", "codigo_material": "MANO-OBRA-POS", "cantidad": 1.00, "nota": "Colocación por metro cuadrado"},
            ],
        },
    }
    if os.path.exists(ruta):
        with open(ruta, "r", encoding="utf-8") as f:
            return json.load(f)
    return embebido


def resolver_partida(codigo_partida, catalogo, cantidad=1.0):
    """Resuelve una partida por código y devuelve su detalle de precios dinámicos."""
    recetas = catalogo.get("partida_receta", {})
    detalles = catalogo.get("partida_receta_detalle", {})
    materiales = catalogo.get("materiales_catalogo", {})

    receta = recetas.get(codigo_partida)
    if not receta:
        return None

    partida_detalle = detalles.get(codigo_partida, [])
    partidas = []
    total = 0.0
    for d in partida_detalle:
        mat = materiales.get(d["codigo_material"])
        if not mat:
            continue
        validar_precio_material(mat)
        qty = d["cantidad"] * cantidad
        precio_unit = mat["precio_base_clp"]
        subtotal = qty * precio_unit
        partidas.append({
            "concepto": f"{mat['nombre']} ({mat['unidad']})",
            "codigo": mat["codigo"],
            "cantidad": qty,
            "unitario": precio_unit,
            "total": subtotal,
            "nota": d.get("nota", ""),
        })
        total += subtotal

    return {
        "codigo_partida": codigo_partida,
        "nombre_partida": receta["nombre_partida"],
        "descripcion": receta.get("descripcion", ""),
        "unidad_medida": receta["unidad_medida"],
        "cantidad": cantidad,
        "partidas": partidas,
        "total": round(total, 0),
    }


class CotizacionPDF(FPDF):
    def __init__(self):
        super().__init__()
        self.set_auto_page_break(auto=True, margin=15)
        self.add_font("DejaVu", "", os.path.join(FONT_DIR, "DejaVuSans.ttf"))
        self.add_font("DejaVu", "B", os.path.join(FONT_DIR, "DejaVuSans-Bold.ttf"))
        self.add_font("DejaVu", "I", os.path.join(FONT_DIR, "DejaVuSans-Oblique.ttf"))
        self.add_font("DejaVu", "BI", os.path.join(FONT_DIR, "DejaVuSans-BoldOblique.ttf"))
        self.set_font("DejaVu", "", 10)

    def header(self):
        self.set_font("DejaVu", "B", 16)
        self.cell(0, 10, "COTIZACIÓN", new_x="LMARGIN", new_y="NEXT", align="C")
        self.set_font("DejaVu", "", 10)
        self.cell(0, 6, "DepaFix - Soluciones en Construcción y Revestimientos", new_x="LMARGIN", new_y="NEXT", align="C")
        self.cell(0, 6, f"Fecha de emisión: {date.today().strftime('%d/%m/%Y')}", new_x="LMARGIN", new_y="NEXT", align="C")
        self.ln(4)

    def datos_cliente(self, cliente, proyecto):
        self.set_font("DejaVu", "B", 11)
        self.cell(0, 7, "Datos del cliente y proyecto", new_x="LMARGIN", new_y="NEXT")
        self.set_font("DejaVu", "", 10)
        self.cell(0, 5, f"Cliente: {cliente}", new_x="LMARGIN", new_y="NEXT")
        self.cell(0, 5, f"Proyecto: {proyecto}", new_x="LMARGIN", new_y="NEXT")
        self.ln(4)

    def tabla_partidas(self, partidas, total):
        self.set_font("DejaVu", "B", 11)
        self.cell(0, 7, "Detalle de partidas", new_x="LMARGIN", new_y="NEXT")
        self.set_font("DejaVu", "B", 8)
        self.cell(10, 7, "Código", border=1)
        self.cell(62, 7, "Concepto", border=1)
        self.cell(28, 7, "Cantidad", border=1, align="C")
        self.cell(30, 7, "Unitario", border=1, align="R")
        self.cell(30, 7, "Total", border=1, align="R")
        self.ln()
        self.set_font("DejaVu", "", 8)
        for p in partidas:
            self.cell(10, 6, p.get("codigo", ""), border=1)
            self.cell(62, 6, p["concepto"], border=1)
            self.cell(28, 6, f"{p['cantidad']:,.2f}", border=1, align="C")
            self.cell(30, 6, f"${p['unitario']:,.0f}", border=1, align="R")
            self.cell(30, 6, f"${p['total']:,.0f}", border=1, align="R")
            self.ln()
            if p.get("nota"):
                self.set_font("DejaVu", "I", 7)
                self.cell(10, 4, "", border=0)
                self.cell(62, 4, f"Nota: {p['nota']}", border=0)
                self.ln()
                self.set_font("DejaVu", "", 8)
        self.cell(100, 6, "TOTAL", border=1, align="R")
        self.cell(40, 6, f"${total:,.0f}", border=1, align="R")
        self.ln(8)

    def clausula_validez(self, texto_clausula):
        self.set_font("DejaVu", "B", 11)
        self.cell(0, 7, "Cláusula de Validez de Cotización", new_x="LMARGIN", new_y="NEXT")
        self.set_font("DejaVu", "", 9)
        lineas = texto_clausula.split("\n")
        for linea in lineas:
            linea = linea.strip()
            if not linea:
                self.ln(2)
                continue
            self.multi_cell(0, 5, linea)
            self.ln(1)
        self.ln(4)

    def firma(self):
        self.set_font("DejaVu", "B", 11)
        self.cell(0, 7, "Aceptación y Firma", new_x="LMARGIN", new_y="NEXT")
        self.ln(6)
        self.cell(80, 6, "Cliente: ______________________________", new_x="LMARGIN", new_y="NEXT")
        self.cell(80, 6, "Fecha: ______________________________", new_x="LMARGIN", new_y="NEXT")
        self.ln(4)
        self.cell(80, 6, "DepaFix: ______________________________", new_x="LMARGIN", new_y="NEXT")
        self.cell(80, 6, "RUT: ______________________________", new_x="LMARGIN", new_y="NEXT")


def generar_pdf(cliente, proyecto, partida_codigo, cantidad=1.0, salida="cotizacion.pdf"):
    catalogo = cargar_catalogo()
    detalle = resolver_partida(partida_codigo, catalogo, cantidad)
    if detalle is None:
        raise ValueError(f"Partida '{partida_codigo}' no encontrada en el catálogo")

    clausula = cargar_clausula()
    pdf = CotizacionPDF()
    pdf.add_page()
    pdf.datos_cliente(cliente, proyecto)
    pdf.tabla_partidas(detalle["partidas"], detalle["total"])
    pdf.clausula_validez(clausula)
    pdf.firma()
    pdf.output(salida)
    return salida, detalle


if __name__ == "__main__":
    salida, detalle = generar_pdf(
        cliente="Cliente Ejemplo",
        proyecto="Instalación cerámica piso",
        partida_codigo="CER-PISO-01",
        cantidad=50.0,
    )
    print(f"PDF generado: {salida}")
    print(f"Partida: {detalle['nombre_partida']} ({detalle['codigo_partida']})")
    print(f"Cantidad: {detalle['cantidad']} {detalle['unidad_medida']}")
    print(f"Total: ${detalle['total']:,.0f}")
