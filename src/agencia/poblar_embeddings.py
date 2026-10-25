"""
poblar_embeddings.py — Llena knowledge_entries.embedding (pgvector 384d) en Supabase.

Toma las filas con embedding NULL, codifica "passage: <contenido>" con
intfloat/multilingual-e5-small (normalizado) y actualiza la columna.
No toca FAISS (data/conocimiento.faiss sigue igual).

Ojo: e5-small lee máximo 512 tokens; el resto del texto se ignora. El dry-run
muestra cuánto de cada fila queda fuera del vector.

Por defecto solo fuente='video_txt' y DRY-RUN.
  --fuente todas   incluye las filas 'youtube' (transcripciones completas)
  --apply          escribe en Supabase
"""
import os
import sys
import logging
import argparse
from collections import Counter

from dotenv import load_dotenv

load_dotenv(".env")
log = logging.getLogger(__name__)

MODELO = "intfloat/multilingual-e5-small"
PREFIJO_PASAJE = "passage: "
PREFIJO_QUERY = "query: "

CONSULTAS_PRUEBA = [
    ("¿Cuánto debería cobrar una agencia por manejar campañas de Meta Ads?", "Pricing_Agencia"),
    ("¿Cómo bajo el costo por clic en Google Ads?", "Google_Ads_CPC"),
    ("¿Conviene más Google o Meta para un negocio local?", "Estrategia_General"),
    ("¿Cómo estructuro campañas, conjuntos de anuncios y anuncios en Meta?", "Meta_Ads_Estructura"),
]


def categoria_de(fila: dict) -> str:
    meta = fila.get("metadata") or {}
    return meta.get("categoria", "-") if isinstance(meta, dict) else "-"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apply", action="store_true", help="Escribir embeddings en Supabase (sin esto: dry-run)")
    parser.add_argument("--fuente", default="video_txt", help="fuente a procesar, o 'todas' (default: video_txt)")
    args = parser.parse_args()

    from supabase import create_client
    url, key = os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not (url and key):
        sys.exit("Faltan SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY en .env")
    client = create_client(url, key)

    query = (client.table("knowledge_entries").select("id, fuente, titulo, contenido, metadata")
             .is_("embedding", "null").order("id"))
    if args.fuente != "todas":
        query = query.eq("fuente", args.fuente)
    filas = [f for f in query.execute().data if (f.get("contenido") or "").strip()]

    print(f"\n{'APPLY' if args.apply else 'DRY-RUN'} — knowledge_entries con embedding NULL "
          f"(fuente={args.fuente}): {len(filas)} filas  {dict(Counter(f['fuente'] for f in filas))}")
    if not filas:
        return

    from sentence_transformers import SentenceTransformer
    modelo = SentenceTransformer(MODELO)
    limite = modelo.max_seq_length

    textos = [PREFIJO_PASAJE + f["contenido"] for f in filas]
    tokens = [len(modelo.tokenizer(t, add_special_tokens=True)["input_ids"]) for t in textos]
    cobertura = [min(1.0, limite / n) for n in tokens]
    truncadas = sum(n > limite for n in tokens)
    print(f"Modelo: {MODELO} (máx {limite} tokens)")
    print(f"Tokens por fila: {min(tokens)}–{max(tokens)} | truncadas: {truncadas}/{len(filas)} | "
          f"texto que entra al vector: promedio {100 * sum(cobertura) / len(cobertura):.0f}%, "
          f"mínimo {100 * min(cobertura):.1f}%")

    emb = modelo.encode(textos, normalize_embeddings=True, batch_size=16,
                        show_progress_bar=False).astype("float32")

    # Prueba de búsqueda sobre los vectores recién calculados (en memoria)
    print("\nPrueba de búsqueda (top 3, a nivel chunk padre):")
    q = modelo.encode([PREFIJO_QUERY + c for c, _ in CONSULTAS_PRUEBA], normalize_embeddings=True)
    sims = q @ emb.T
    for (consulta, esperada), fila_sims in zip(CONSULTAS_PRUEBA, sims):
        top = fila_sims.argsort()[::-1][:3]
        aciertos = sum(categoria_de(filas[i]) == esperada for i in top)
        print(f"  ❓ {consulta}  [{aciertos}/3 de {esperada}]")
        for i in top:
            print(f"     {fila_sims[i]:.3f}  {categoria_de(filas[i]):<22} {filas[i]['titulo'][:55]}")

    if not args.apply:
        print("\n(dry-run: no se escribió nada. Usa --apply para actualizar Supabase.)")
        return

    for j, fila in enumerate(filas):
        vector = "[" + ",".join(f"{x:.7f}" for x in emb[j]) + "]"  # literal pgvector
        client.table("knowledge_entries").update({"embedding": vector}).eq("id", fila["id"]).execute()
    restantes = (client.table("knowledge_entries").select("id", count="exact")
                 .is_("embedding", "null").execute().count)
    log.info(f"✅ {len(filas)} embeddings actualizados. Quedan {restantes} filas con embedding NULL en total.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    main()
