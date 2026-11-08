#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Validación de ingesta — Nivel 2 (Búsqueda semántica de prueba).

Supervisor DepaFix.
Ejecuta una búsqueda semántica de prueba sobre la tabla unificada de
documentos en Supabase con el texto:
    "presupuesto instalación cerámica 50 m2 Macul Ñuñoa"

Imprime los TOP 5 resultados (content y similarity) para revisar si hay
"contaminación semántica" entre cálculos abstractos y cotizaciones reales.

Requisitos de entorno (.env):
  SUPABASE_URL=https://<proyecto>.supabase.co
  SUPABASE_SERVICE_ROLE_KEY=<service_role_key>
  SUPABASE_TABLA_DOCUMENTOS=<nombre de la tabla unificada>   (opcional, default: documentos)
  SUPABASE_MODELO_EMBEDDINGS=intfloat/multilingual-e5-small   (opcional)

La tabla unificada debe tener, al menos:
  id bigint, contenido text, metadata jsonb (con campo "tipo"),
  embedding vector(384), created_at timestamptz
y una función RPC match_<tabla>(query_embedding, match_threshold, match_count).

Uso:
  python3 scripts/validar_ingesta_nivel2.py
  # con filtro de tipo (solo cotizaciones):
  python3 scripts/validar_ingesta_nivel2.py --tipo cotizacion
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

# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip()
SUPABASE_KEY = (
    os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    or os.getenv("SUPABASE_KEY", "").strip()
)
TABLA = os.getenv("SUPABASE_TABLA_DOCUMENTOS", "documentos").strip()
MODELO_EMBEDDINGS = os.getenv("SUPABASE_MODELO_EMBEDDINGS", "intfloat/multilingual-e5-small").strip()
QUERY_PRUEBA = "presupuesto instalación cerámica 50 m2 Macul Ñuñoa"
TOP_K = 5
MATCH_THRESHOLD = 0.0


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


def rpc_nombre(tabla: str) -> str:
    return f"match_{tabla}"


def extraer_contenido(fila: Dict[str, Any]) -> str:
    for campo in ("contenido", "content", "texto"):
        valor = fila.get(campo)
        if valor:
            return str(valor).strip()
    return ""


def buscar_por_rpc(cliente: Client, tabla: str, vector: List[float], k: int, tipo: Optional[str]) -> List[Dict[str, Any]]:
    """Intenta la función RPC match_<tabla>. Devuelve [{contenido, metadata, similarity}]."""
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
                "metadata": fila.get("metadata") or {},
                "similarity": fila.get("similarity"),
            }
            for fila in filas
            if extraer_contenido(fila)
        ]
    except Exception as error:
        print(f"  ⚠️  RPC '{rpc_nombre(tabla)}' no disponible: {str(error)[:140]}")
        print("  🔁  Usando búsqueda directa sobre la tabla (fallback en Python)...")
        return buscar_directo(cliente, tabla, vector, k, tipo)


def buscar_directo(cliente: Client, tabla: str, vector: List[float], k: int, tipo: Optional[str]) -> List[Dict[str, Any]]:
    """Fallback: trae registros y calcula similitud coseno en Python."""
    # Pedimos un sobremuestreo para poder filtrar por tipo y seguir teniendo k resultados.
    fetch_count = max(k * 10, 100)
    respuesta = (
        cliente.table(tabla)
        .select("contenido,metadata,embedding")
        .limit(fetch_count)
        .execute()
    )
    filas = respuesta.data or []
    consulta = np.asarray(vector, dtype=float)
    norma_consulta = np.linalg.norm(consulta)
    puntuados = []
    for fila in filas:
        texto = extraer_contenido(fila)
        if not texto:
            continue
        if tipo is not None:
            meta = fila.get("metadata") or {}
            if isinstance(meta, str):
                try:
                    meta = json.loads(meta)
                except (TypeError, ValueError):
                    meta = {}
            if not isinstance(meta, dict) or meta.get("tipo") != tipo:
                continue
        embedding = fila.get("embedding")
        similitud = 0.0
        if embedding is not None and norma_consulta > 0:
            try:
                if isinstance(embedding, str):
                    embedding = json.loads(embedding)
                doc = np.asarray(embedding, dtype=float)
                denominador = norma_consulta * np.linalg.norm(doc)
                if denominador > 0:
                    similitud = float(np.dot(consulta, doc) / denominador)
            except (TypeError, ValueError, json.JSONDecodeError):
                similitud = 0.0
        puntuados.append((similitud, texto, fila.get("metadata") or {}))
    puntuados.sort(key=lambda item: item[0], reverse=True)
    return [
        {"contenido": texto, "metadata": metadata, "similarity": similitud}
        for similitud, texto, metadata in puntuados[:k]
    ]


def imprimir_resultados(resultados: List[Dict[str, Any]], etiqueta: str) -> None:
    print("\n" + "=" * 70)
    print(f"RESULTADOS TOP {TOP_K} — {etiqueta}")
    print("=" * 70)
    if not resultados:
        print("(sin resultados)")
        return
    for indice, fila in enumerate(resultados, start=1):
        meta = fila.get("metadata") or {}
        tipo = meta.get("tipo", "?")
        origen = meta.get("origen", meta.get("fuente", "?"))
        sim = fila.get("similarity")
        sim_txt = f"{sim:.4f}" if isinstance(sim, (int, float)) else "N/A"
        contenido = fila.get("contenido", "")
        print(f"\n[{indice}] similarity={sim_txt} | tipo={tipo} | origen={origen}")
        print("-" * 70)
        print(contenido)


def main() -> None:
    parser = argparse.ArgumentParser(description="Validación Nivel 2 — búsqueda semántica Supabase")
    parser.add_argument("--tipo", default=None, help="Filtrar por metadata.tipo (ej: cotizacion). Default: sin filtro")
    args = parser.parse_args()

    print("🧭 DepaFix Supervisor — Validación Nivel 2 (Búsqueda semántica)")
    print(f"   Query de prueba : {QUERY_PRUEBA}")
    print(f"   Tabla           : {TABLA}")
    print(f"   Modelo          : {MODELO_EMBEDDINGS}")
    print(f"   Filtro tipo     : {args.tipo or '(ninguno — se revisa contaminación)'}")
    print(f"   Top-K           : {TOP_K}")

    cliente = crear_cliente()
    print("✅ Cliente Supabase creado")

    modelo = SentenceTransformer(MODELO_EMBEDDINGS)
    print("✅ Modelo de embeddings cargado")

    vector = generar_embedding(QUERY_PRUEBA, modelo)
    print("✅ Embedding de la consulta generado")

    resultados = buscar_por_rpc(cliente, TABLA, vector, TOP_K, args.tipo)
    imprimir_resultados(resultados, f"tabla={TABLA}" + (f" | tipo={args.tipo}" if args.tipo else ""))

    # Señal de contaminación: si no hay filtro y los 5 primeros son de tipo calculo,
    # el query está siendo capturado por cálculos abstractos y no por cotizaciones.
    if args.tipo is None and resultados:
        tipos = [str((r.get("metadata") or {}).get("tipo", "?")) for r in resultados]
        hay_cotizaciones = any(t == "cotizacion" for t in tipos)
        print("\n" + "=" * 70)
        if not hay_cotizaciones:
            print("⚠️  ALERTA: Los top-5 NO contienen cotizaciones reales.")
            print("   Existe riesgo de contaminación semántica con cálculos abstractos.")
            print("   Aplicar filtro metadata->>'tipo' = 'cotizacion' (ver Tarea 2).")
        else:
            print("✅ OK: Entre los top-5 hay al menos una cotización real.")
        print("=" * 70)


if __name__ == "__main__":
    main()
