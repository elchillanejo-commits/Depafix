#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Ejecuta la validación de precios scrapeados y marca los inválidos.

Flujo:
  1. Conecta a Supabase.
  2. Trae `precios_historial` de los últimos 30 días.
     Equivalente SQL:
         SELECT id, producto_id, precio_neto, precio_lista, url_producto,
                fecha_scrapeo, es_valido
           FROM precios_historial
          WHERE fecha_scrapeo >= now() - interval '30 days'
          ORDER BY producto_id, fecha_scrapeo;
  3. Pasa el DataFrame por validar_precios_scrapeados().
  4. Actualiza a es_valido = false los registros detectados como basura.

Uso:
    .venv/bin/python src/data/run_validacion.py
    .venv/bin/python src/data/run_validacion.py --dias 30
"""

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd
from dotenv import load_dotenv
from supabase import create_client

sys.path.insert(0, str(Path(__file__).resolve().parent))
from validador_precios import validar_precios_scrapeados

COLUMNAS = [
    "id",
    "producto_id",
    "precio_neto",
    "precio_lista",
    "url_producto",
    "fecha_scrapeo",
    "es_valido",
]
TAMANO_LOTE = 200


def cargar_env() -> None:
    candidatos = [
        Path(__file__).resolve().parents[2] / ".env",
        Path.home() / "DepaFix_Maestro" / ".env",
        Path.cwd() / ".env",
    ]
    for ruta in candidatos:
        if ruta.exists():
            load_dotenv(ruta)
            return
    load_dotenv()


def get_supabase():
    cargar_env()
    url = os.getenv("SUPABASE_URL")
    key = (
        os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        or os.getenv("SUPABASE_KEY")
        or os.getenv("SUPABASE_ANON_KEY")
    )
    if not url or not key:
        raise RuntimeError(
            "Faltan SUPABASE_URL y SUPABASE_SERVICE_ROLE_KEY/SUPABASE_KEY en .env"
        )
    return create_client(url, key)


def traer_precios(sb, dias: int) -> pd.DataFrame:
    corte = (datetime.now(timezone.utc) - timedelta(days=dias)).isoformat()
    respuesta = (
        sb.table("precios_historial")
        .select(",".join(COLUMNAS))
        .gte("fecha_scrapeo", corte)
        .order("producto_id")
        .order("fecha_scrapeo")
        .execute()
    )
    print(f"[1/4] Registros de los últimos {dias} días: {len(respuesta.data)}")
    return pd.DataFrame(respuesta.data, columns=COLUMNAS)


def marcar_invalidos(sb, df: pd.DataFrame) -> List[Dict[str, Any]]:
    invalidos = df[df["es_valido"] == False].copy()  # noqa: E712
    if invalidos.empty:
        print("[4/4] No hay registros para marcar como inválidos.")
        return []

    ids = [int(x) for x in invalidos["id"].tolist()]
    print(f"[4/4] Marcando {len(ids)} registro(s) con es_valido = false...")

    for inicio in range(0, len(ids), TAMANO_LOTE):
        lote = ids[inicio:inicio + TAMANO_LOTE]
        sb.table("precios_historial").update(
            {"es_valido": False}
        ).in_("id", lote).execute()

    detalle = []
    for _, fila in invalidos.iterrows():
        detalle.append(
            {
                "id": int(fila["id"]),
                "producto_id": fila["producto_id"],
                "precio_neto": float(fila["precio_neto"]),
                "precio_lista": float(fila["precio_lista"]),
                "fecha_scrapeo": str(fila["fecha_scrapeo"]),
                "url_producto": fila.get("url_producto"),
            }
        )
    return detalle


def ejecutar_validacion(dias: int = 30, sb=None) -> Dict[str, int]:
    """Valida precios de los últimos N días y marca los inválidos.

    Devuelve un resumen reutilizable por otros scripts (por ejemplo, el
    scraper de Sodimac al finalizar una extracción).
    """
    if sb is None:
        sb = get_supabase()

    df = traer_precios(sb, dias)
    if df.empty:
        print("[2/4] Sin datos en el período. Nada que validar.")
        return {"total": 0, "validos": 0, "invalidos": 0}

    print("[2/4] Ejecutando validar_precios_scrapeados()...")
    df = validar_precios_scrapeados(df)

    total = len(df)
    validos = int((df["es_valido"] == True).sum())  # noqa: E712
    invalidos = int((df["es_valido"] == False).sum())  # noqa: E712
    print(
        f"[3/4] Resultado: {total} registros | "
        f"válidos={validos} | inválidos={invalidos}"
    )

    detalle = marcar_invalidos(sb, df)
    if detalle:
        print("\nPrecios basura detectados:")
        for item in detalle:
            print(
                f"  - id={item['id']} producto_id={item['producto_id']} "
                f"neto=${item['precio_neto']:,.0f} "
                f"lista=${item['precio_lista']:,.0f} "
                f"fecha={item['fecha_scrapeo']}"
            )
            if item.get("url_producto"):
                print(f"    {item['url_producto']}")

    consulta = (
        sb.table("precios_historial")
        .select("id", count="exact")
        .eq("es_valido", False)
        .execute()
    )
    print(f"\nTotal es_valido=false en precios_historial: {consulta.count}")
    return {"total": total, "validos": validos, "invalidos": invalidos}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Valida precios de los últimos N días y marca es_valido=false"
    )
    parser.add_argument("--dias", type=int, default=30, help="Ventana en días")
    args = parser.parse_args()

    ejecutar_validacion(args.dias)
    return 0


if __name__ == "__main__":
    sys.exit(main())
