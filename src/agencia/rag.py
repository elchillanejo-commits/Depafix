"""
rag.py — Consulta al conocimiento cargado por ingestar_videos.py.

Busca en Supabase con pgvector (función match_knowledge sobre knowledge_chunks,
ver 07_IKKI_MARKETING/sql/09_pgvector_knowledge_chunks.sql) y devuelve los
chunks padre completos (~700 palabras) de knowledge_entries.

La pregunta se codifica como "query: <texto>" con multilingual-e5-small vía
ONNX (embeddings_onnx.py), sin torch, para que corra en Railway.
"""
import os
import logging
from functools import lru_cache

from dotenv import load_dotenv

from src.agencia.embeddings_onnx import a_pgvector, codificar_query

load_dotenv(".env")
log = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _cliente():
    from supabase import create_client
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])


def buscar(consulta: str, k: int = 3, categoria: str | None = None) -> list[dict]:
    """Devuelve hasta k chunks padre distintos: {parent_id, titulo, categoria, score, contenido}."""
    filas = _cliente().rpc("match_knowledge", {
        "query_embedding": a_pgvector(codificar_query(consulta)),
        "match_count": k,
        "filtro_categoria": categoria,
    }).execute().data
    return [{
        "parent_id": f["entry_id"],
        "titulo": f["titulo"],
        "categoria": f["categoria"],
        "score": float(f["similitud"]),
        "contenido": f["contenido"],
    } for f in filas]


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
