#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
validar_ingesta.py — Validación de ingesta para coach_tierra.

- Args: --query, --tabla, --k, --tipo
- Genera embedding de la query con intfloat/multilingual-e5-small (384 dims).
- Llama a la RPC match_<tabla> enviando p_tipo.
- Fallback: filtra metadata->>'tipo' directamente en Supabase y calcula
  similitud coseno en Python.
- Imprime top-K con content + similarity.
- Advierte si ningún resultado tiene el tipo solicitado.
"""

import argparse
import json
import os
import sys
from typing import Any, Dict, List, Optional

import numpy as np
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
from supabase import Client, create_client

load_dotenv()
load_dotenv(os.path.expanduser("~/.depafix_secrets"))

SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip()
SUPABASE_KEY = (
    os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    or os.getenv("SUPABASE_KEY", "").strip()
)
MODELO_EMBEDDINGS = os.getenv(
    "SUPABASE_MODELO_EMBEDDINGS", "intfloat/multilingual-e5-small"
).strip()
MATCH_THRESHOLD = 0.0
LOTE_FALLBACK = 1000
MAX_FALLBACK = 5000


def crear_cliente() -> Client:
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise SystemExit(
            "Faltan SUPABASE_URL y SUPABASE_SERVICE_ROLE_KEY en .env o ~/.depafix_secrets"
        )
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def generar_embedding(texto: str, modelo: SentenceTransformer) -> List[float]:
    vector = modelo.encode(f"query: {texto}", normalize_embeddings=True)
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
    norma_a = np.linalg.norm(a)
    norma_b = np.linalg.norm(b)
    if norma_a == 0 or norma_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norma_a * norma_b))


def rpc_nombre(tabla: str) -> str:
    return f"match_{tabla}"


def buscar_por_rpc(
    cliente: Client,
    tabla: str,
    vector: List[float],
    k: int,
    tipo: Optional[str],
) -> List[Dict[str, Any]]:
    try:
        params: Dict[str, Any] = {
            "query_embedding": vector,
            "match_threshold": MATCH_THRESHOLD,
            "match_count": k,
        }
        if tipo is not None:
            params["p_tipo"] = tipo
        respuesta = cliente.rpc(rpc_nombre(tabla), params).execute()
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
        print(f"  ⚠️  RPC '{rpc_nombre(tabla)}' no disponible: {str(error)[:140]}")
        print("  🔁  Usando búsqueda directa sobre la tabla (fallback en Python)...")
        return buscar_directo(cliente, tabla, vector, k, tipo)


def buscar_directo(
    cliente: Client,
    tabla: str,
    vector: List[float],
    k: int,
    tipo: Optional[str],
) -> List[Dict[str, Any]]:
    consulta = np.asarray(vector, dtype=float)
    filas: List[Dict[str, Any]] = []
    start = 0
    while True:
        query = cliente.table(tabla).select("contenido,metadata,embedding")
        if tipo is not None:
            query = query.filter("metadata->>tipo", "eq", tipo)
        respuesta = query.range(start, start + LOTE_FALLBACK - 1).execute()
        lote = respuesta.data or []
        filas.extend(lote)
        if len(lote) < LOTE_FALLBACK:
            break
        start += LOTE_FALLBACK
        if len(filas) >= MAX_FALLBACK:
            break

    puntuados = []
    for fila in filas:
        texto = extraer_contenido(fila)
        if not texto:
            continue
        meta = parse_metadata(fila.get("metadata"))
        if tipo is not None and meta.get("tipo") != tipo:
            continue
        embedding = fila.get("embedding")
        similitud = 0.0
        if embedding is not None:
            try:
                if isinstance(embedding, str):
                    embedding = json.loads(embedding)
                doc = np.asarray(embedding, dtype=float)
                similitud = similitud_coseno(consulta, doc)
            except (TypeError, ValueError, json.JSONDecodeError):
                similitud = 0.0
        puntuados.append((similitud, texto, meta))
    puntuados.sort(key=lambda item: item[0], reverse=True)
    return [
        {"contenido": texto, "metadata": meta, "similarity": similitud}
        for similitud, texto, meta in puntuados[:k]
    ]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validación de ingesta — coach_tierra"
    )
    parser.add_argument("--query", required=True, help="Texto de consulta")
    parser.add_argument(
        "--tabla", required=True, help="Nombre de tabla (ej: coach_tierra)"
    )
    parser.add_argument("--k", type=int, required=True, help="Número de resultados")
    parser.add_argument(
        "--tipo", required=True, help="Filtro metadata.tipo (ej: cotizacion)"
    )
    args = parser.parse_args()

    print("🧭 Validación de ingesta")
    print(f"   Query           : {args.query}")
    print(f"   Tabla           : {args.tabla}")
    print(f"   K               : {args.k}")
    print(f"   Tipo solicitado : {args.tipo}")
    print(f"   Modelo          : {MODELO_EMBEDDINGS}")

    cliente = crear_cliente()
    print("✅ Cliente Supabase creado")

    modelo = SentenceTransformer(MODELO_EMBEDDINGS)
    print("✅ Modelo de embeddings cargado")

    vector = generar_embedding(args.query, modelo)
    print("✅ Embedding de la consulta generado")

    resultados = buscar_por_rpc(cliente, args.tabla, vector, args.k, args.tipo)

    print("\n" + "=" * 80)
    print(f"TOP {args.k} — tabla={args.tabla} | tipo={args.tipo}")
    print("=" * 80)
    if not resultados:
        print("(sin resultados)")
        print("\n⚠️  ADVERTENCIA: Ningún resultado tiene el tipo solicitado.")
        print("=" * 80)
        sys.exit(0)

    tipos_encontrados = []
    for indice, fila in enumerate(resultados, start=1):
        meta = fila.get("metadata") or {}
        tipo_res = meta.get("tipo", "?")
        tipos_encontrados.append(tipo_res)
        origen = meta.get(
            "origen", meta.get("fuente", meta.get("archivo", meta.get("ruta", "?")))
        )
        sim = fila.get("similarity")
        sim_txt = f"{sim:.4f}" if isinstance(sim, (int, float)) else "N/A"
        contenido = fila.get("contenido", "")
        print(f"\n[{indice}] similarity={sim_txt} | tipo={tipo_res} | origen={origen}")
        print("-" * 80)
        print(contenido[:2000])
        if len(contenido) > 2000:
            print("\n... (truncado)")

    if all(t != args.tipo for t in tipos_encontrados):
        print("\n" + "=" * 80)
        print("⚠️  ADVERTENCIA: Ningún resultado tiene el tipo solicitado.")
        print("=" * 80)
    else:
        print("\n" + "=" * 80)
        print("✅ OK: Hay resultados con el tipo solicitado.")
        print("=" * 80)


if __name__ == "__main__":
    main()
