#!/usr/bin/env python3
"""Consulta los tres fragmentos de Metal más relevantes para una pregunta."""

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
from supabase import create_client

MODELO = "intfloat/multilingual-e5-small"
TABLA = "metal_knowledge"
RPC = "match_metal_knowledge"
CANTIDAD_RESULTADOS = 3
TAMANO_PAGINA = 1000


def obtener_pregunta() -> str:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pregunta", nargs="*", help="Pregunta entre comillas")
    args = parser.parse_args()

    pregunta = " ".join(args.pregunta).strip()
    if not pregunta:
        pregunta = input("Pregunta para Metal: ").strip()
    if not pregunta:
        raise ValueError("Debes ingresar una pregunta.")
    return pregunta


def obtener_cliente():
    load_dotenv(Path(__file__).resolve().parent / ".env")
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise RuntimeError(
            "Faltan SUPABASE_URL o SUPABASE_SERVICE_ROLE_KEY en el archivo .env."
        )
    return create_client(url, key)


def buscar_por_rpc(supabase, vector_pregunta):
    respuesta = supabase.rpc(
        RPC,
        {
            "query_embedding": vector_pregunta,
            "match_threshold": 0.0,
            "match_count": CANTIDAD_RESULTADOS,
        },
    ).execute()
    return respuesta.data or []


def convertir_vector(vector) -> np.ndarray:
    if isinstance(vector, str):
        vector = json.loads(vector)
    return np.asarray(vector, dtype=float)


def buscar_con_respaldo(supabase, vector_pregunta):
    """Calcula la similitud localmente si la función RPC no está disponible."""
    filas = []
    inicio = 0
    while True:
        respuesta = (
            supabase.table(TABLA)
            .select("contenido,metadata,embedding")
            .range(inicio, inicio + TAMANO_PAGINA - 1)
            .execute()
        )
        lote = respuesta.data or []
        filas.extend(lote)
        if len(lote) < TAMANO_PAGINA:
            break
        inicio += TAMANO_PAGINA

    consulta = convertir_vector(vector_pregunta)
    norma_consulta = np.linalg.norm(consulta)
    resultados = []
    for fila in filas:
        try:
            documento = convertir_vector(fila["embedding"])
            denominador = norma_consulta * np.linalg.norm(documento)
            if denominador == 0:
                continue
            similitud = float(np.dot(consulta, documento) / denominador)
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            continue
        resultados.append({**fila, "similitud": similitud})

    resultados.sort(key=lambda fila: fila["similitud"], reverse=True)
    return resultados[:CANTIDAD_RESULTADOS]


def buscar(supabase, vector_pregunta):
    try:
        return buscar_por_rpc(supabase, vector_pregunta)[:CANTIDAD_RESULTADOS]
    except Exception as error:
        print(
            f"La función RPC no está disponible ({error}). "
            "Se usará la búsqueda local de respaldo.",
            file=sys.stderr,
        )
        return buscar_con_respaldo(supabase, vector_pregunta)


def obtener_fuente(resultado) -> str:
    metadata = resultado.get("metadata") or {}
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except json.JSONDecodeError:
            metadata = {}
    return metadata.get("fuente", "Fuente no indicada")


def obtener_similitud(resultado):
    for campo in ("similarity", "similitud", "score"):
        if resultado.get(campo) is not None:
            return float(resultado[campo])
    return None


def mostrar_resultados(pregunta, resultados):
    print(f"Pregunta: {pregunta}")
    print("=" * 72)
    if not resultados:
        print("No se encontraron fragmentos en metal_knowledge.")
        return

    for indice, resultado in enumerate(resultados, start=1):
        similitud = obtener_similitud(resultado)
        puntaje = f"{similitud:.4f}" if similitud is not None else "N/D"
        contenido = (resultado.get("contenido") or "").strip()
        print(
            f"\n[{indice}] Similitud: {puntaje} | "
            f"Fuente: {obtener_fuente(resultado)}\n"
        )
        print(contenido or "Fragmento sin contenido.")


def main() -> int:
    try:
        pregunta = obtener_pregunta()
        supabase = obtener_cliente()
        print(f"Cargando modelo {MODELO}...", file=sys.stderr)
        modelo = SentenceTransformer(MODELO)
        vector_pregunta = modelo.encode(
            f"query: {pregunta}", normalize_embeddings=True
        ).tolist()
        resultados = buscar(supabase, vector_pregunta)
        mostrar_resultados(pregunta, resultados)
        return 0 if resultados else 1
    except KeyboardInterrupt:
        print("\nConsulta cancelada.", file=sys.stderr)
        return 130
    except Exception as error:
        print(f"Error al consultar Metal: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
