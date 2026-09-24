"""youtube_batch.py — Ingesta masiva de YouTube."""
import asyncio
import logging
from datetime import datetime, timezone

from ceo.workers.youtube import youtube_ingest_worker

logger = logging.getLogger(__name__)


async def youtube_batch_worker(params: dict) -> dict:
    """Ingesta masiva de URLs de YouTube."""
    urls = params.get("urls", [])
    tags_comunes = params.get("tags_comunes", [])

    if not urls:
        return {"ok": False, "error": "Falta parámetro 'urls' (lista)"}

    resultados = []
    exitosas = 0
    fallidas = 0

    for url in urls:
        try:
            r = await youtube_ingest_worker({"url": url, "tags": tags_comunes})
            if r.get("ok"):
                exitosas += 1
                resultados.append({
                    "url": url,
                    "ok": True,
                    "knowledge_id": r.get("knowledge_id"),
                    "titulo": r.get("titulo"),
                })
            else:
                fallidas += 1
                resultados.append({
                    "url": url,
                    "ok": False,
                    "error": r.get("error"),
                })
        except Exception as e:
            fallidas += 1
            resultados.append({
                "url": url,
                "ok": False,
                "error": str(e)[:150],
            })
        await asyncio.sleep(2)  # rate limit YouTube

    return {
        "ok": True,
        "total": len(urls),
        "exitosas": exitosas,
        "fallidas": fallidas,
        "resultados": resultados,
        "ejecutado": datetime.now(timezone.utc).isoformat(),
    }
