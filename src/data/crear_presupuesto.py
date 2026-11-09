#!/usr/bin/env python3
# -*- coding: utf-8 :-
"""Script principal: JSON con múltiples partidas -> cotización -> PDF en output/."""

import argparse
import sys
import json
import math
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

from src.data import cotizador
from src.data.pdf_generator import generar_pdf

RAIZ = Path(__file__).resolve().parents[2]
OUTPUT_DIR = RAIZ / "output"


def procesar_presupuesto(id_cotizacion: str, datos_proyecto: dict, ruta_salida: str) -> dict:
    """
    Procesa un proyecto con múltiples partidas.

    Parámetros:
        id_cotizacion (str): Identificador de la cotización (p.ej. UUID o nombre).
        datos_proyecto (dict): Debe contener una clave 'items' con una lista de dicts,
                               cada dict con al menos 'sku' y 'cantidad' (superficie en m2).
        ruta_salida (str): Ruta donde se generará el PDF.

    Retorna:
        dict: {'subtotal_venta_neto': float, 'monto_iva': float, 'total_presupuesto_bruto': float}
    """
    partidas = []
    subtotal_venta_neto = 0.0
    monto_iva = 0.0
    total_presupuesto_bruto = 0.0
    param_globales = None

    for item in datos_proyecto.get("items", []):
        sku = item["sku"]
        try:
            # Obtener información del producto y precio
            precio_info = cotizador.obtener_ultimo_precio(sku)
            prod = precio_info["producto"]
            material_name = prod.get("categoria", "").strip()
            if not material_name:
                raise ValueError(f"SKU {sku} no tiene categoría definida")

            # Cargar rendimientos del material
            rendimientos = cotizador.load_material_rendimientos()
            match_key = None
            for key, val in rendimientos.items():
                if key.lower() == material_name.lower():
                    match_key = key
                    break
            if match_key is None:
                raise ValueError(f"Material '{material_name}' no encontrado en rendimientos_materiales.json")

            rendimiento = rendimientos[match_key]["rendimiento"]
            desperdicio_pct = rendimientos[match_key]["desperdicio_pct"]

            # Calcular cantidad comercial
            superficie = float(item["cantidad"])
            unidades_teoricas = superficie / rendimiento
            unidades_con_desperdicio = unidades_teoricas * (1 + desperdicio_pct / 100)
            unidades_comerciales = math.ceil(unidades_con_desperdicio)

            # Generar cotización para este SKU y superficie
            cotiz = cotizador.generar_cotizacion(superficie, sku)
            if not cotiz.get("partidas"):
                raise ValueError(f"No se obtuvo partida para SKU {sku}")

            partida = cotiz["partidas"][0]  # asumimos una sola partida por SKU
            partidas.append(partida)

            # Acumular totales financieros
            subtotal_venta_neto += cotiz["resumen_financiero"]["precio_venta_neto_total"]
            monto_iva += cotiz["resumen_financiero"]["iva_total"]
            total_presupuesto_bruto += cotiz["resumen_financiero"]["precio_venta_con_iva_total"]

            # Guardar parámetros globales del primer ítem válido
            if param_globales is None:
                param_globales = cotiz["parametros_globales"]

        except Exception as e:
            print(f"Advertencia: SKU {sku} no procesado - {e}", file=sys.stderr)
            continue

    if not partidas:
        raise ValueError("No se procesó ningún ítem válido")

    # Construir el JSON final de la cotización
    cotizacion_final = {
        "id_cotizacion": id_cotizacion,
        "parametros_globales": param_globales,
        "partidas": partidas,
        "resumen_financiero": {
            "costo_directo_neto_total": sum(p["costo_directo_neto"] for p in partidas),
            "precio_venta_neto_total": subtotal_venta_neto,
            "iva_total": monto_iva,
            "precio_venta_con_iva_total": total_presupuesto_bruto,
            "utilidad_neta_total": sum(p.get("utilidad", 0) for p in partidas),
            "margen_utilidad_pct": 0.30 * 100,
        },
    }

    # Generar PDF
    generar_pdf(cotizacion_final, ruta_salida)

    return {
        "subtotal_venta_neto": subtotal_venta_neto,
        "monto_iva": monto_iva,
        "total_presupuesto_bruto": total_presupuesto_bruto,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Genera un presupuesto PDF a partir de un archivo JSON con múltiples partidas."
    )
    parser.add_argument("json_file", help="Archivo JSON con array de materiales")
    args = parser.parse_args()

    # Cargar JSON
    try:
        with open(args.json_file, "r", encoding="utf-8") as f:
            materiales = json.load(f)
    except Exception as e:
        print(f"Error al leer el archivo JSON: {e}", file=sys.stderr)
        return 1

    if not isinstance(materiales, list):
        print("Error: el JSON debe contener una lista de materiales.", file=sys.stderr)
        return 1

    todas_partidas: List[Dict[str, Any]] = []
    suma_costo = 0.0
    suma_venta_neto = 0.0
    suma_iva = 0.0
    suma_venta_iva = 0.0
    suma_utilidad = 0.0

    for mat in materiales:
        sku = mat["sku"]
        if "cantidad_m2" in mat:
            superficie = float(mat["cantidad_m2"])
        elif "cantidad_unidades" in mat:
            superficie = float(mat["cantidad_unidades"])
        else:
            print(f"Error: material {sku} debe tener cantidad_m2 o cantidad_unidades.", file=sys.stderr)
            return 1

        cotizacion = cotizador.generar_cotizacion(superficie, sku)
        if not cotizacion.get("partidas"):
            print(f"Error: no se obtuvo partida para SKU {sku}.", file=sys.stderr)
            return 1

        partida = cotizacion["partidas"][0]  # asumimos una sola partida por SKU
        todas_partidas.append(partida)

        suma_costo += partida["costo_directo_neto"]
        suma_venta_neto += cotiz["resumen_financiero"]["precio_venta_neto_total"]
        suma_iva += cotiz["resumen_financiero"]["iva_total"]
        suma_venta_iva += cotiz["resumen_financiero"]["precio_venta_con_iva_total"]
        suma_utilidad += cotiz["resumen_financiero"].get("utilidad_neta_total", 0.0)

    # Parámetros globales (usar datos del primer material)
    primer = todas_partidas[0] if todas_partidas else {}
    param_globales = {
        "sku": primer.get("sku_solicitado", primer.get("sku", "")),
        "descripcion": primer.get("descripcion", ""),
        "categoria": primer.get("categoria"),
        "superficie_m2": sum(
            m["superficie_m2"] if "superficie_m2" in m else 0
            for m in materiales
        ),
        "rendimiento_m2_por_galon": 15.0,
        "desperdicio_pct": 0.10 * 100,
        "margen_pct": 0.30 * 100,
        "iva_pct": 0.19 * 100,
        "moneda": "CLP",
        "precio_unitario_neto": primer.get("precio_unitario_neto", 0.0),
        "precio_unitario_lista": primer.get("precio_unitario_lista", 0.0),
        "precio_fuente_url": primer.get("url_producto", ""),
        "precio_fecha_scrapeo": primer.get("fecha_scrapeo", ""),
        "fecha_cotizacion": datetime.now().isoformat(),
    }

    resumen_financiero = {
        "costo_directo_neto_total": round(suma_costo, 2),
        "precio_venta_neto_total": round(suma_venta_neto, 2),
        "iva_total": round(suma_iva, 2),
        "precio_venta_con_iva_total": round(suma_venta_iva, 2),
        "utilidad_neta_total": round(suma_utilidad, 2),
        "margen_utilidad_pct": 0.30 * 100,
    }

    cotizacion_final = {
        "id_cotizacion": datetime.now().strftime("%Y%m%d%H%M%S") + "-" + "-".join(
            [p["sku"] for p in todas_partidas[:3]]
        ),
        "parametros_globales": param_globales,
        "partidas": todas_partidas,
        "resumen_financiero": resumen_financiero,
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    marca = datetime.now().strftime("%Y%m%d_%H%M%S")
    salida = OUTPUT_DIR / f"presupuesto_multi_{marca}.pdf"

    generar_pdf(cotizacion_final, salida)

    print(f"PDF generado en: {salida}")
    print(f"TOTAL a cobrar: ${cotizacion_final['resumen_financiero']['precio_venta_con_iva_total']:,.0f}".replace(",", "."))

    return 0


if __name__ == "__main__":
    sys.exit(main())