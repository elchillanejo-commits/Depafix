from __future__ import annotations
import os
from supabase import create_client
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv
import logging

load_dotenv()
logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger(__name__)

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

def main():
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    LOGGER.info("Cargando modelo de embeddings...")
    model = SentenceTransformer("intfloat/multilingual-e5-small")

    LOGGER.info("Buscando chunks sin embedding...")
    total_updated = 0

    while True:
        resp = supabase.table("knowledge_chunks_v2").select("id, content").is_("embedding", "null").limit(100).execute()
        chunks = resp.data
        if not chunks:
            break

        LOGGER.info(f"Vectorizando {len(chunks)} chunks...")
        texts = [c["content"] for c in chunks]
        embeddings = model.encode(texts, normalize_embeddings=True)

        for i, chunk in enumerate(chunks):
            emb_list = embeddings[i].tolist()
            supabase.table("knowledge_chunks_v2").update({"embedding": emb_list}).eq("id", chunk["id"]).execute()
            total_updated += 1
    
    LOGGER.info(f"Proceso terminado. {total_updated} chunks actualizados.")

if __name__ == "__main__":
    main()
