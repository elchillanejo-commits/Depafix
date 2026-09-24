"""query.py — Busca en knowledge_items por keyword."""
import logging
import os
from datetime import datetime, timezone

from dotenv import load_dotenv
from supabase import create_client

load_dotenv(os.path.expanduser("~/PROYECTOS/Proyectos/DepaFix/.env"))
logger = logging.getLogger(__name__)


async def query_knowledge_worker(params: dict) -> dict:
    """Busca en knowledge_items."""
    keyword = params.get("keyword", "").strip()
    limite = params.get("limite", 10)
    source = params.get("source")

    if not keyword:
        return {"ok": False, "error": "Falta parámetro 'keyword'"}

    client = create_client(
        os.getenv("SUPABASE_URL"),
        os.getenv("SUPABASE_SERVICE_ROLE_KEY"),
    )

    query = client.table("knowledge_items").select("id,source,title,autor,contenido,url,creado_en")
    if source:
        query = query.eq("source", source)
    query = query.ilike("contenido", f"%{keyword}%").limit(limite)

    try:
        resp = query.execute()
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}

    resultados = []
    for item in resp.data or []:
        contenido = item.get("contenido", "")
        idx = contenido.lower().find(keyword.lower())
        inicio = max(0, idx - 100)
        fragmento = contenido[inicio:inicio + 300] if idx >= 0 else contenido[:300]

        resultados.append({
            "id": item["id"],
            "source": item.get("source"),
            "title": item.get("title"),
            "autor": item.get("autor"),
            "fragmento": fragmento.strip(),
            "url": item.get("url"),
            "creado_en": item.get("creado_en"),
        })

    return {
        "ok": True,
        "keyword": keyword,
        "total": len(resultados),
        "resultados": resultados,
        "ejecutado": datetime.now(timezone.utc).isoformat(),
    }
