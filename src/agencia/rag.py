"""
rag.py — Consulta al conocimiento cargado por ingestar_videos.py.

Busca en data/conocimiento.faiss (sub-fragmentos de ~150 palabras) y devuelve
los chunks padre completos (~700 palabras) desde knowledge_entries en Supabase.
El modelo y el prefijo de consulta se leen de data/conocimiento.faiss.json,
así siempre coinciden con los usados al indexar (multilingual-e5-small, "query: ").
"""
import os
import json
import sqlite3
import logging
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv(".env")
log = logging.getLogger(__name__)

FAISS_PATH = "data/conocimiento.faiss"
FAISS_META_PATH = "data/conocimiento.faiss.json"
DB_PATH = "data/conocimiento.db"


@lru_cache(maxsize=1)
def _cargar():
    import faiss
    from sentence_transformers import SentenceTransformer

    with open(FAISS_META_PATH, "r", encoding="utf-8") as f:
        config = json.load(f)
    index = faiss.read_index(FAISS_PATH)
    con = sqlite3.connect(DB_PATH)
    docs = [json.loads(m) for (m,) in con.execute("SELECT metadata FROM documentos ORDER BY id")]
    con.close()
    if len(docs) != index.ntotal:
        raise RuntimeError(f"Índice desalineado: {index.ntotal} vectores vs {len(docs)} filas en documentos. "
                           "Corre src/agencia/ingestar_videos.py --apply")
    modelo = SentenceTransformer(config["modelo"])
    if modelo.get_sentence_embedding_dimension() != index.d:
        raise RuntimeError(f"El modelo {config['modelo']} no coincide con la dimensión del índice ({index.d})")
    return config, index, docs, modelo


def buscar(consulta: str, k: int = 3, categoria: str | None = None) -> list[dict]:
    """Devuelve hasta k chunks padre distintos: {parent_id, titulo, categoria, score, contenido}."""
    config, index, docs, modelo = _cargar()
    q = modelo.encode([config["prefijo_query"] + consulta], normalize_embeddings=True).astype("float32")
    # Pedimos de más: varios sub-fragmentos pueden caer en el mismo padre o en otra categoría
    puntajes, ids = index.search(q, min(index.ntotal, k * 10 if categoria is None else index.ntotal))

    mejores = {}
    for score, i in zip(puntajes[0], ids[0]):
        if i < 0:
            continue
        d = docs[i]
        if categoria and d["categoria"] != categoria:
            continue
        if d["parent_id"] not in mejores:
            mejores[d["parent_id"]] = {"parent_id": d["parent_id"], "titulo": d["titulo"],
                                       "categoria": d["categoria"], "score": float(score)}
        if len(mejores) == k:
            break

    if not mejores:
        return []
    from supabase import create_client
    client = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])
    filas = (client.table("knowledge_entries").select("id, contenido")
             .in_("id", list(mejores)).execute().data)
    contenido = {str(f["id"]): f["contenido"] for f in filas}
    resultados = []
    for pid, r in mejores.items():
        r["contenido"] = contenido.get(str(pid), "")
        resultados.append(r)
    return resultados


def obtener_contexto_relevante(consulta: str, k: int = 3, categoria: str | None = None) -> str:
    """Texto listo para el {contexto_rag} de prompt_engineer.construir_prompt."""
    bloques = [f"--- {r['titulo']} ({r['categoria']}) ---\n{r['contenido']}"
               for r in buscar(consulta, k, categoria)]
    return "\n\n".join(bloques)


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.WARNING)
    pregunta = " ".join(sys.argv[1:]) or "¿Cómo bajo el costo por clic en Google Ads?"
    for r in buscar(pregunta):
        print(f"{r['score']:.3f}  [{r['categoria']}] {r['titulo'][:60]}  (id {r['parent_id']}, "
              f"{len(r['contenido'].split())} palabras)")
