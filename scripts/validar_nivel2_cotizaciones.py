#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Validación Nivel 2 — Búsqueda semántica filtrada por cotizaciones en coach_tierra.
Supervisor DepaFix.

Ejecuta una búsqueda semántica de prueba sobre Supabase (tabla coach_tierra)
con el texto "presupuesto cerámica 50m2 Macul", filtrando únicamente filas
con metadata->>'tipo' = 'cotizacion', e imprime los TOP 5 (content y similarity).

Requisitos de entorno (.env):
  SUPABASE_URL=https://<proyecto>.supabase.co
  SUPABASE_SERVICE_ROLE_KEY=<service_role_key>

La función RPC public.match_coach_tierra(query_embedding, match_count, p_tipo)
debe existir en Supabase (ver Tarea 2). Si no existe, el script usa fallback
de búsqueda directa con filtro en Python y sobremuestreo.
"""

import argparse
import json
import os
from typing import Any, Dict, List, Optional

import numpy as np
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
from supabase import Client, create_client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip()
SUPABASE_KEY = (
    os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    or os.getenv("SUPABASE_KEY", "").strip()
)
TABLA_DEFAULT = "coach_tierra"
MODELO_DEFAULT = "intfloat/multilingual-e5-small"
QUERY_PRUEBA = "presupuesto cerámica 50m2 Macul"
TOP_K = 5


def crear_cliente() -> Client:
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise SystemExit(
            "Faltan SUPABASE_URL y SUPABASE_SERVICE_ROLE_KEY en el .env"
        )
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def generar_embedding(texto: str, modelo: SentenceTransformer) -> List[float]:
    """Embedding consistente con el agente CEO: prefijo 'query: ' y normalizado."""
    vector = modelo.encode(
        f"query: {texto}",
        normalize_embeddings=True,
    )
    return vector.tolist()


def extraer_contenido(fila: Dict[str, Any]) -> str:
    for campo in ("contenido", "content", "texto"):
        valor = fila.get(campo)
        if valor:
            return str(valor).strip()
    return ""


def parse_metadata(valor: Any) -> Dict[str, Any]:
    if valor is None:
        return {}
    if isinstance(valor, dict):
        return valor
    if isinstance(valor, str):
        try:
            return json.loads(valor)
        except (TypeError, ValueError):
            return {}
    return {}


def similitud_coseno(a: np.ndarray, b: np.ndarray) -> float:
    na = np.linalg.norm(a)
    nb = np.linalg.norm(b)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def buscar_por_rpc(
    cliente: Client,
    tabla: str,
    vector: List[float],
    k: int,
    tipo: Optional[str],
) -> List[Dict[str, Any]]:
    rpc = f"match_{tabla}"
    try:
        params: Dict[str, Any] = {
            "query_embedding": vector,
            "match_threshold": 0.0,
            "match_count": k,
        }
        if tipo is not None:
            params["p_tipo"] = tipo
        respuesta = cliente.rpc(rpc, params).execute()
        filas = respuesta.data or []
        return [
            {
                "contenido": extraer_contenido(fila),
                "metadata": parse_metadata(fila.get("metadata")),
                "similarity": fila.get("similarity"),
            }
            for fila in filas
            if extraer_contenido(fila)
        ]
    except Exception as error:
        print(f"  [WARN] RPC '{rpc}' no disponible: {str(error)[:160]}")
        print("  [FALLBACK] Usando búsqueda directa sobre la tabla...")
        return buscar_directo(cliente, tabla, vector, k, tipo)


def buscar_directo(
    cliente: Client,
    tabla: str,
    vector: List[float],
    k: int,
    tipo: Optional[str],
) -> List[Dict[str, Any]]:
    """Fallback: filtra por tipo directamente en Supabase, calcula similitud coseno."""
    consulta = np.asarray(vector, dtype=float)
    filas = []
    start = 0
    limit_batch = 1000
    while True:
        query = cliente.table(tabla).select("contenido,metadata,embedding")
        if tipo is not None:
            query = query.filter("metadata->>tipo", "eq", tipo)
        respuesta = query.range(start, start + limit_batch - 1).execute()
        lote = respuesta.data or []
        filas.extend(lote)
        if len(lote) < limit_batch:
            break
        start += limit_batch
        if len(filas) > 5000:
            break

    puntuados = []
    for fila in filas:
        texto = extraer_contenido(fila)
        if not texto:
            continue
        meta = parse_metadata(fila.get("metadata"))
        if tipo is not None and meta.get("tipo") != tipo:
            continue
        emb = fila.get("embedding")
        sim = 0.0
        if emb is not None:
            try:
                if isinstance(emb, str):
                    emb = json.loads(emb)
                doc = np.asarray(emb, dtype=float)
                sim = similitud_coseno(consulta, doc)
            except (TypeError, ValueError, json.JSONDecodeError):
                sim = 0.0
        puntuados.append((sim, texto, meta))
    puntuados.sort(key=lambda item: item[0], reverse=True)
    return [
        {"contenido": texto, "metadata": meta, "similarity": sim}
        for sim, texto, meta in puntuados[:k]
    ]


def imprimir_resultados(
    resultados: List[Dict[str, Any]],
    tabla: str,
    tipo: Optional[str],
    k: int,
) -> None:
    print("\n" + "=" * 70)
    etiqueta = f"tabla={tabla}" + (f" | tipo={tipo}" if tipo else "")
    print(f"RESULTADOS TOP {k} - {etiqueta}")
    print("=" * 70)
    if not resultados:
        print("(sin resultados)")
        return
    for indice, fila in enumerate(resultados, start=1):
        meta = fila.get("metadata") or {}
        sim = fila.get("similarity")
        sim_txt = f"{sim:.4f}" if isinstance(sim, (int, float)) else "N/A"
        contenido = fila.get("contenido", "")
        print(f"\n[{indice}] similarity={sim_txt} | tipo={meta.get('tipo', '?')}")
        print("-" * 70)
        print(contenido)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validación Nivel 2 - búsqueda semántica filtrada por cotizaciones en Supabase"
    )
    parser.add_argument(
        "--tipo",
        default="cotizacion",
        help="Valor de metadata.tipo a filtrar (default: cotizacion)",
    )
    parser.add_argument(
        "--tabla",
        default=TABLA_DEFAULT,
        help=f"Tabla de Supabase (default: {TABLA_DEFAULT})",
    )
    parser.add_argument(
        "--query",
        default=QUERY_PRUEBA,
        help="Texto de consulta",
    )
    parser.add_argument(
        "--k",
        type=int,
        default=TOP_K,
        help="Cantidad de resultados (default: 5)",
    )
    args = parser.parse_args()

    print("DepaFix Supervisor - Validación Nivel 2 (Búsqueda semántica filtrada)")
    print(f"   Query      : {args.query}")
    print(f"   Tabla      : {args.tabla}")
    print(f"   Filtro tipo: {args.tipo}")
    print(f"   Top-K      : {args.k}")
    print(f"   Modelo     : {MODELO_DEFAULT}")

    cliente = crear_cliente()
    print("[OK] Cliente Supabase creado")

    modelo = SentenceTransformer(MODELO_DEFAULT)
    print("[OK] Modelo de embeddings cargado")

    vector = generar_embedding(args.query, modelo)
    print("[OK] Embedding de la consulta generado")

    resultados = buscar_por_rpc(cliente, args.tabla, vector, args.k, args.tipo)
    imprimir_resultados(resultados, args.tabla, args.tipo, args.k)

    if args.tipo is not None and resultados:
        tipos = [str((r.get("metadata") or {}).get("tipo", "?")) for r in resultados]
        if all(t != args.tipo for t in tipos):
            print("\n[ALERTA] Ningún resultado tiene el tipo solicitado.")
            print("   Verifica que las filas de coach_tierra tengan metadata.tipo poblado.")
        else:
            print(f"\n[OK] Resultados filtrados por tipo='{args.tipo}'.")


if __name__ == "__main__":
    main()
