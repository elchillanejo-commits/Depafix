#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Inserta materiales de una cotizacion PDF en public.proyecto_materiales.

No genera PDFs ni aplica margenes: registra el costo real del proveedor y deja
la fila en estado 'pendiente' para seguimiento de compra.

Uso:
  python insertar_materiales.py \
      --pdf "ruta/al/presupuesto.pdf" \
      --proyecto "PRY-VERBENAS-8925" \
      --proveedor "AMD MANTENCIONES" \
      --sku-prefix AMD \
      [--fecha-requerida 2026-11-15] [--dry-run]
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

import pdfplumber
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip()
SUPABASE_KEY = (
    os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    or os.getenv("SUPABASE_KEY", "").strip()
)

COLUMNAS = {
    "codigo": ("CODIGO", "CÓDIGO", "SKU", "COD"),
    "descripcion": ("DESCRIP", "CONCEPTO", "ITEM", "PARTIDA"),
    "unidad": ("UNID", "U.M", "UM"),
    "cantidad": ("CANT",),
    "precio": ("PRECIO UNIT", "P. UNIT", "UNITARIO", "PRECIO"),
    "total": ("TOTAL",),
}
EXCLUIDAS = ("SUB-TOTAL", "SUBTOTAL", "TOTAL", "IVA", "DESCUENTO")
MONTO_RE = re.compile(r"\$\s?\d[\d.,]*")
CANTIDAD_UNIDAD_RE = re.compile(
    r"(?<![\d.])(\d+(?:[.,]\d+)?)\s*(m2|m²|m\s*2|ml|m|un|gl|kg|lt|l)\b",
    re.IGNORECASE,
)


def parsear_numero(texto):
    s = (texto or "").replace("$", "").replace(" ", "").strip()
    if not s:
        return None
    if re.fullmatch(r"-?\d{1,3}(\.\d{3})+(,\d+)?", s):
        s = s.replace(".", "").replace(",", ".")
    else:
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def normalizar(texto):
    return re.sub(r"\s+", " ", texto or "").strip()


def detectar_columnas(fila):
    celdas = [str(c or "").upper() for c in fila]
    mapa = {}
    for campo, claves in COLUMNAS.items():
        for i, celda in enumerate(celdas):
            if any(clave in celda for clave in claves) and i not in mapa.values():
                mapa[campo] = i
                break
    if "descripcion" in mapa and "precio" in mapa:
        return mapa
    return None


def es_encabezado(texto):
    t = texto.upper()
    return "CANT" in t and ("PRECIO" in t or "UNIT" in t)


def parsear_fila_columnas(fila, mapa):
    celdas = [str(c or "").strip() for c in fila]

    def celda(campo):
        idx = mapa.get(campo)
        return celdas[idx] if idx is not None and idx < len(celdas) else ""

    descripcion = celda("descripcion")
    if not descripcion or any(p in descripcion.upper() for p in EXCLUIDAS):
        return None
    precio = parsear_numero(celda("precio"))
    if precio is None:
        return None
    cantidad = parsear_numero(celda("cantidad"))
    total = parsear_numero(celda("total"))
    if cantidad is None and total and precio:
        cantidad = total / precio
    if cantidad is None:
        return None
    return {
        "codigo": celda("codigo"),
        "concepto": descripcion,
        "unidad": celda("unidad") or "un",
        "cantidad": cantidad,
        "precio_unitario": precio,
    }


def parsear_linea(linea):
    """Parsea filas que pdfplumber devuelve como una sola celda combinada."""
    texto = normalizar(linea)
    if not texto or any(p in texto.upper() for p in EXCLUIDAS):
        return None
    if es_encabezado(texto):
        return None

    montos = [parsear_numero(m.group(0)) for m in MONTO_RE.finditer(texto)]
    montos = [m for m in montos if m is not None]
    if not montos:
        return None

    precio = montos[-2] if len(montos) >= 2 else montos[-1]

    primer_monto = texto.find("$")
    antes = texto[:primer_monto] if primer_monto != -1 else texto
    coincidencias = list(CANTIDAD_UNIDAD_RE.finditer(antes))

    if coincidencias:
        m = coincidencias[-1]
        cantidad = parsear_numero(m.group(1))
        unidad = m.group(2).replace(" ", "").lower()
        if unidad in ("m", "m2", "m²"):
            unidad = "m2"
        descripcion = antes[:m.start()].strip(" -")
    else:
        cantidad = 1.0
        unidad = "gl"
        descripcion = antes.strip(" -")

    descripcion = re.sub(r"^\d+\s+\d+\s+", "", descripcion).strip()
    if cantidad is None or not descripcion or len(descripcion) < 3:
        return None

    return {
        "codigo": "",
        "concepto": descripcion,
        "unidad": unidad,
        "cantidad": cantidad,
        "precio_unitario": precio,
    }


def extraer_partidas(ruta_pdf):
    partidas = []
    with pdfplumber.open(ruta_pdf) as pdf:
        for pagina in pdf.pages:
            for tabla in pagina.extract_tables():
                mapa = detectar_columnas(tabla[0]) if tabla else None
                for fila in tabla:
                    if mapa:
                        partida = parsear_fila_columnas(fila, mapa)
                        if partida:
                            partidas.append(partida)
                            continue
                    partida = parsear_linea(" ".join(str(c or "") for c in fila))
                    if partida:
                        partidas.append(partida)

    if not partidas:
        raise SystemExit(
            "No se encontraron partidas. El PDF debe tener una tabla con "
            "encabezados DESCRIPCION / CANTIDAD / PRECIO UNITARIO."
        )
    return partidas


def crear_cliente():
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise SystemExit("Faltan SUPABASE_URL y SUPABASE_SERVICE_ROLE_KEY en .env")
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def construir_registros(partidas, args):
    registros = []
    for i, p in enumerate(partidas, start=1):
        sku = (p.get("codigo") or "").strip() or f"{args.sku_prefix}-{i:03d}"
        registros.append({
            "proyecto_codigo": args.proyecto,
            "material_sku": sku,
            "descripcion": p["concepto"],
            "proveedor": args.proveedor,
            "unidad": p["unidad"] or "un",
            "cantidad_aprobada": p["cantidad"],
            "cantidad_comprada": 0,
            "precio_unitario_real_clp": round(p["precio_unitario"], 2),
            "estado_compra": args.estado,
            "fecha_requerida": args.fecha_requerida,
            "notas": f"Importado desde {Path(args.pdf).name}",
        })
    return registros


def main():
    parser = argparse.ArgumentParser(description="Inserta materiales de un PDF en Supabase.")
    parser.add_argument("--pdf", required=True, help="PDF de la cotizacion del proveedor")
    parser.add_argument("--proyecto", required=True, help="Codigo del proyecto")
    parser.add_argument("--proveedor", required=True, help="Nombre del proveedor")
    parser.add_argument("--sku-prefix", default="AUTO", help="Prefijo si el PDF no trae SKU")
    parser.add_argument("--fecha-requerida", default=None, help="Fecha requerida en obra (YYYY-MM-DD)")
    parser.add_argument(
        "--estado",
        default="pendiente",
        choices=("pendiente", "cotizando", "ordenado", "comprado", "recibido", "instalado", "cancelado"),
    )
    parser.add_argument("--dry-run", action="store_true", help="Muestra los registros sin insertar")
    args = parser.parse_args()

    ruta = Path(args.pdf)
    if not ruta.exists():
        raise SystemExit(f"No existe el PDF: {ruta}")

    partidas = extraer_partidas(ruta)
    registros = construir_registros(partidas, args)

    print(f"Partidas detectadas: {len(registros)}")
    if args.dry_run:
        print(json.dumps(registros, ensure_ascii=False, indent=2, default=str))
        return

    cliente = crear_cliente()
    respuesta = (
        cliente.table("proyecto_materiales")
        .upsert(
            registros,
            on_conflict="proyecto_codigo,material_sku,descripcion",
            ignore_duplicates=True,
        )
        .execute()
    )
    filas = respuesta.data or []
    print(f"Registros insertados/actualizados: {len(filas)}")
    for fila in filas:
        print(
            f"  id={fila.get('id')} | SKU={fila.get('material_sku')} | "
            f"{fila.get('descripcion')} | cant={fila.get('cantidad_aprobada')} | "
            f"estado={fila.get('estado_compra')}"
        )


if __name__ == "__main__":
    sys.exit(main())
