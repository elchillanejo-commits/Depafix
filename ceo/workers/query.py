import os
import logging
from datetime import datetime, timezone
from supabase import create_client

logger = logging.getLogger(__name__)

async def query_knowledge_worker(params: dict) -> dict:
    """Busca en knowledge_items."""
    keyword = params.get("keyword")
    limite = params.get("limite", 10)
    source = params.get("source")
    
    if not keyword:
        return {"ok": False, "error": "Falta keyword"}
        
    client = create_client(
        os.getenv("SUPABASE_URL"),
        os.getenv("SUPABASE_SERVICE_ROLE_KEY"),
    )
    
    query = client.table("knowledge_items").select("id,source,title,autor,url,contenido,creado_en")
    
    # Simulación de búsqueda en múltiples campos con OR en Supabase
    # Nota: ilike en una sola columna es simple. Para múltiples, se requiere OR.
    # Esta es una aproximación:
    search_pattern = f"%{keyword}%"
    
    # Debido a limitaciones de .or() en la librería de python, esta es la forma más directa:
    # Filtramos por título O contenido O autor.
    # Se usa .or_("title.ilike.{p},contenido.ilike.{p},autor.ilike.{p}")
    query = query.or_(f"title.ilike.{search_pattern},contenido.ilike.{search_pattern},autor.ilike.{search_pattern}")
    
    if source:
        query = query.eq("source", source)
        
    results = query.limit(limite).execute().data or []
    
    # Procesar resultados (fragmento)
    resultados_formateados = []
    for r in results:
        contenido = r.get("contenido", "")
        # Encontrar primer match para fragmento
        idx = contenido.lower().find(keyword.lower())
        fragmento = contenido[max(0, idx-50):idx+150] if idx != -1 else contenido[:200]
        
        resultados_formateados.append({
            "id": r["id"],
            "source": r["source"],
            "title": r["title"],
            "autor": r["autor"],
            "fragmento": fragmento + "...",
            "url": r["url"],
            "creado_en": r["creado_en"]
        })
        
    return {
        "keyword": keyword,
        "total": len(resultados_formateados),
        "resultados": resultados_formateados,
        "ejecutado": datetime.now(timezone.utc).isoformat()
    }
