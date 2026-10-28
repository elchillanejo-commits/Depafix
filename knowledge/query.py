"""Consulta semántica sobre knowledge_chunks_v2."""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any

from dotenv import load_dotenv
from supabase import Client, create_client

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")

LOGGER = logging.getLogger(__name__)

MODEL_NAME = "intfloat/multilingual-e5-small"
PREFIJO_CONSULTA = "query: "
RPC_NAME = "match_knowledge_v2"


@lru_cache(maxsize=1)
def _get_client() -> Client:
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise RuntimeError("Faltan SUPABASE_URL o SUPABASE_SERVICE_ROLE_KEY en el .env")
    return create_client(url, key)


@lru_cache(maxsize=1)
def _get_model() -> SentenceTransformer:
    from sentence_transformers import SentenceTransformer

    LOGGER.info("Cargando modelo %s...", MODEL_NAME)
    return SentenceTransformer(MODEL_NAME)


def _to_pgvector(vector: Any) -> str:
    return "[" + ",".join(f"{float(value):.7f}" for value in vector) + "]"


def _embed_question(question: str) -> str:
    vector = _get_model().encode(
        PREFIJO_CONSULTA + question,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    if len(vector) != 384:
        raise RuntimeError(f"El modelo devolvió {len(vector)} dimensiones; se esperaban 384")
    return _to_pgvector(vector)


def query_knowledge(question: str, domain: str | None = None, n: int = 5) -> list[dict]:
    """Devuelve los n chunks más similares: content, source_file y score."""
    question = (question or "").strip()
    if not question:
        raise ValueError("question no puede estar vacía")
    if n <= 0:
        raise ValueError("n debe ser mayor que 0")

    domain = domain.strip() if domain else None
    params: dict[str, Any] = {
        "query_embedding": _embed_question(question),
        "match_count": n,
    }
    if domain:
        params["filtro_domain"] = domain

    LOGGER.debug("Consultando %s (domain=%s, n=%d)", RPC_NAME, domain, n)
    try:
        rows = _get_client().rpc(RPC_NAME, params).execute().data or []
    except Exception as exc:
        message = str(exc)
        if "Could not find the function" in message or "PGRST202" in message:
            raise RuntimeError(
                "La función RPC match_knowledge_v2 no existe en Supabase. "
                "Ejecuta sql/12_match_knowledge_v2.sql en el SQL Editor."
            ) from exc
        raise

    return [
        {
            "content": row["content"],
            "source_file": row["source_file"],
            "score": float(row["score"]),
        }
        for row in rows
    ]


if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Consulta semántica de knowledge_chunks_v2")
    parser.add_argument("question")
    parser.add_argument("--domain", default=None)
    parser.add_argument("-n", type=int, default=5)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    print(json.dumps(query_knowledge(args.question, args.domain, args.n), ensure_ascii=False, indent=2))
