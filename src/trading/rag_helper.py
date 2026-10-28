import os
import logging
from supabase import create_client
from sentence_transformers import SentenceTransformer

log = logging.getLogger(__name__)
_modelo = None

def _get_modelo():
    global _modelo
    if _modelo is None:
        log.info("Cargando modelo intfloat/multilingual-e5-small...")
        _modelo = SentenceTransformer("intfloat/multilingual-e5-small")
    return _modelo

def consultar_conocimiento(pregunta, limite=2):
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        return "Error: Faltan credenciales de Supabase"
    try:
        client = create_client(url, key)
        modelo = _get_modelo()
        vector = modelo.encode(f"query: {pregunta}").tolist()
        resp = client.rpc("match_knowledge", {
            "query_embedding": vector,
            "match_count": limite,
            "filtro_categoria": None
        }).execute()
        if not resp.data:
            return "No se encontró conocimiento previo."
        return "\n".join([f"[{r['titulo']}]: {r['contenido'][:300]}..." for r in resp.data])
    except Exception as e:
        log.error(f"Error consultando RAG: {e}")
        return f"Error RAG: {e}"

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv(os.path.expanduser("~/PROYECTOS/Proyectos/DepaFix/.env"))
    if not os.environ.get("SUPABASE_URL"):
        os.environ["SUPABASE_URL"] = os.popen("grep SUPABASE_URL ~/.depafix_secrets | cut -d'=' -f2").read().strip()
        os.environ["SUPABASE_SERVICE_ROLE_KEY"] = os.popen("grep SUPABASE_SERVICE_ROLE_KEY ~/.depafix_secrets | cut -d'=' -f2").read().strip()
    print("=== Probando el Cerebro RAG ===")
    print(consultar_conocimiento("¿Qué hago si el RSI está bajo y toca Golden Pocket?"))
