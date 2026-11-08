#!/usr/bin/env python3
import os
import re
import sys
import unicodedata
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client
from sentence_transformers import SentenceTransformer

load_dotenv(Path(__file__).with_name(".env"))

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")
MODELO_EMBEDDINGS = "intfloat/multilingual-e5-small"

UMBRAL_SIMILITUD = 0.84
MATCH_THRESHOLD = 0.35
MATCH_COUNT = 3

# Cada pregunta puede exigir terminos en el fragmento top-1.
PREGUNTAS = (
    {
        "pregunta": "¿Qué documentos se necesitan para sacar la OS-10?",
        "requiere_top1": (),
    },
    {
        "pregunta": "¿Cuál es el proceso para certificar una OTEC con SCI?",
        "requiere_top1": (),
    },
    {
        "pregunta": "¿Qué dice la No Conformidad F-248 sobre el contrato de arriendo?",
        "requiere_top1": ("no conformidad", "contrato de arriendo"),
    },
)

# El documento fuente usa "arrendamiento"; se acepta como equivalente de "arriendo".
PATRONES_TERMINOS = {
    "contrato de arriendo": re.compile(r"contrato de arri(?:endo|endamiento)"),
}


def normalizar(texto):
    descompuesto = unicodedata.normalize("NFKD", str(texto or ""))
    sin_acentos = "".join(c for c in descompuesto if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", sin_acentos).lower().strip()


def contiene_termino(texto_normalizado, termino):
    patron = PATRONES_TERMINOS.get(termino)
    if patron:
        return bool(patron.search(texto_normalizado))
    return normalizar(termino) in texto_normalizado


def main():
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("[ERROR] Faltan SUPABASE_URL y SUPABASE_SERVICE_ROLE_KEY en el .env")
        sys.exit(1)

    cliente = create_client(SUPABASE_URL, SUPABASE_KEY)
    print("Cargando modelo de embeddings...")
    modelo = SentenceTransformer(MODELO_EMBEDDINGS)

    aprobadas = 0
    resumen = []

    for numero, item in enumerate(PREGUNTAS, 1):
        pregunta = item["pregunta"]
        requiere = item["requiere_top1"]

        vector = modelo.encode(
            f"query: {pregunta}",
            show_progress_bar=False,
        ).tolist()

        respuesta = cliente.rpc(
            "match_coach_otec",
            {
                "query_embedding": vector,
                "match_threshold": MATCH_THRESHOLD,
                "match_count": MATCH_COUNT,
            },
        ).execute()
        resultados = respuesta.data or []

        print("\n" + "=" * 70)
        print(f"PREGUNTA {numero}: {pregunta}")
        print("=" * 70)

        if not resultados:
            print("  [WARN] Sin resultados sobre el umbral de recuperacion.")
            resumen.append((numero, "FAIL", ["sin resultados"]))
            continue

        for posicion, fila in enumerate(resultados, 1):
            metadata = fila.get("metadata") or {}
            print(
                f"\n[{posicion}] similitud={fila.get('similarity', 0):.4f} "
                f"tipo={metadata.get('tipo', '?')}"
            )
            print(f"    archivo: {metadata.get('archivo', '?')}")
            contenido = (fila.get("contenido") or "").replace("\n", " ")
            print(f"    {contenido[:300]}...")

        top1 = resultados[0]
        similitud = top1.get("similarity", 0) or 0
        contenido_top1 = normalizar(top1.get("contenido"))

        similitud_ok = similitud > UMBRAL_SIMILITUD
        faltantes = [t for t in requiere if not contiene_termino(contenido_top1, t)]
        terminos_ok = not faltantes
        estado = "PASS" if similitud_ok and terminos_ok else "FAIL"
        if estado == "PASS":
            aprobadas += 1

        print("\n  VALIDACION TOP-1")
        print(
            f"    similitud: {similitud:.4f} "
            f"({'>' if similitud_ok else '<='} {UMBRAL_SIMILITUD}: "
            f"{'OK' if similitud_ok else 'FALLA'})"
        )
        if requiere:
            print(
                "    terminos: "
                + ("OK" if terminos_ok else f"FALTAN {faltantes}")
            )
        print(f"    estado: {estado}")

        resumen.append((numero, estado, faltantes))

    print("\n" + "=" * 70)
    print(f"RESUMEN QA: {aprobadas}/{len(PREGUNTAS)} preguntas PASS")
    print("=" * 70)
    for numero, estado, faltantes in resumen:
        detalle = f" - faltan: {faltantes}" if faltantes else ""
        print(f"  P{numero}: {estado}{detalle}")

    if aprobadas != len(PREGUNTAS):
        sys.exit(1)


if __name__ == "__main__":
    main()
