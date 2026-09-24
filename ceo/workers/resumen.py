"""resumen.py — Resume knowledge_items con Claude API."""
import logging
import os
from datetime import datetime, timezone

from dotenv import load_dotenv
from supabase import create_client

# Carga de envs: si no hay archivo, no pasa nada (Railway usa env vars nativas)
load_dotenv()
logger = logging.getLogger(__name__)


async def resumen_ia_worker(params: dict) -> dict:
    """Resume items pendientes con Claude."""
    limite = params.get("limite", 5)

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return {"ok": False, "error": "Falta ANTHROPIC_API_KEY"}

    try:
        import anthropic
    except ImportError:
        return {"ok": False, "error": "anthropic no instalado. pip install anthropic"}

    client = create_client(
        os.getenv("SUPABASE_URL"),
        os.getenv("SUPABASE_SERVICE_ROLE_KEY"),
    )

    pendientes = (
        client.table("knowledge_items")
        .select("id,title,contenido")
        .eq("procesado", False)
        .limit(limite)
        .execute()
    ).data or []

    if not pendientes:
        return {"ok": True, "procesados": 0, "mensaje": "No hay items pendientes"}

    anthropic_client = anthropic.Anthropic(api_key=api_key)
    procesados = 0
    fallidos = 0
    ejemplos = []

    for item in pendientes:
        try:
            contenido = (item.get("contenido") or "")[:8000]
            resp = anthropic_client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=300,
                messages=[{
                    "role": "user",
                    "content": f"Resume este transcript en 3 oraciones ejecutivas en español:\n\n{contenido}",
                }],
            )
            resumen = resp.content[0].text.strip()

            client.table("knowledge_items").update({
                "resumen": resumen,
                "procesado": True,
            }).eq("id", item["id"]).execute()

            procesados += 1
            if len(ejemplos) < 3:
                ejemplos.append({
                    "knowledge_id": item["id"],
                    "titulo": item.get("title"),
                    "resumen": resumen,
                })
        except Exception as e:
            logger.error(f"Error procesando {item['id']}: {e}")
            fallidos += 1

    return {
        "ok": True,
        "procesados": procesados,
        "fallidos": fallidos,
        "ejemplos": ejemplos,
        "ejecutado": datetime.now(timezone.utc).isoformat(),
    }
