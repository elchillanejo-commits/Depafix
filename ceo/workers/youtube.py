"""youtube.py — Descarga transcript de YouTube a knowledge_items."""
import asyncio
import logging
import os
import re
from datetime import datetime, timezone

import requests
from dotenv import load_dotenv
from supabase import create_client
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    TranscriptsDisabled,
    NoTranscriptFound,
    VideoUnavailable,
)

load_dotenv(os.path.expanduser("~/PROYECTOS/Proyectos/DepaFix/.env"))
logger = logging.getLogger(__name__)


def _extraer_video_id(url: str) -> str | None:
    """Extrae video_id de cualquier formato de URL de YouTube."""
    patrones = [
        r"(?:v=|/v/|youtu\.be/|/embed/|/shorts/)([a-zA-Z0-9_-]{11})",
    ]
    for p in patrones:
        m = re.search(p, url)
        if m:
            return m.group(1)
    return None


def _obtener_metadatos(url: str) -> dict:
    """Obtiene título y autor vía oEmbed de YouTube."""
    try:
        oembed = f"https://www.youtube.com/oembed?url={url}&format=json"
        r = requests.get(oembed, timeout=10)
        if r.status_code == 200:
            data = r.json()
            return {
                "titulo": data.get("title", ""),
                "autor": data.get("author_name", ""),
            }
    except Exception as e:
        logger.warning(f"oEmbed falló: {e}")
    return {"titulo": "", "autor": ""}


async def youtube_ingest_worker(params: dict) -> dict:
    """
    Descarga transcript de YouTube y lo guarda en knowledge_items.
    
    Params:
        url: URL del video
        tags: lista de tags opcionales
    """
    url = params.get("url", "").strip()
    tags = params.get("tags", [])

    if not url:
        return {"ok": False, "error": "Falta parámetro 'url'"}

    video_id = _extraer_video_id(url)
    if not video_id:
        return {"ok": False, "error": f"URL no es de YouTube: {url}"}

    logger.info(f"Procesando YouTube: {video_id}")

    # 1. Descargar transcript (API nueva v1.x)
    try:
        api = YouTubeTranscriptApi()
        fetched = api.fetch(video_id, languages=["es", "en"])
        # Convertir snippets a lista de dicts (compatibilidad)
        transcript_list = [
            {"text": s.text, "start": s.start, "duration": s.duration}
            for s in fetched.snippets
        ]
    except TranscriptsDisabled:
        return {"ok": False, "error": "Subtítulos deshabilitados"}
    except NoTranscriptFound:
        return {"ok": False, "error": "No hay transcript disponible"}
    except VideoUnavailable:
        return {"ok": False, "error": "Video no disponible"}
    except Exception as e:
        return {"ok": False, "error": f"YouTube error: {str(e)[:150]}"}

    # 2. Concatenar en texto plano
    contenido = " ".join(frag.get("text", "") for frag in transcript_list)
    contenido = contenido.strip()

    if not contenido:
        return {"ok": False, "error": "Transcript vacío"}

    # 3. Duración aproximada
    duracion_seg = 0
    if transcript_list:
        last = transcript_list[-1]
        duracion_seg = int(last.get("start", 0) + last.get("duration", 0))

    # 4. Metadatos (en thread para no bloquear el loop)
    meta = await asyncio.to_thread(_obtener_metadatos, url)

    # 5. Guardar en Supabase
    client = create_client(
        os.getenv("SUPABASE_URL"),
        os.getenv("SUPABASE_SERVICE_ROLE_KEY"),
    )

    registro = {
        "source": "youtube",
        "url": url,
        "title": meta["titulo"] or f"YouTube {video_id}",
        "autor": meta["autor"],
        "contenido": contenido,
        "tags": tags,
        "duracion_seg": duracion_seg,
        "procesado": False,
    }

    resp = client.table("knowledge_items").insert(registro).execute()

    if not resp.data:
        return {"ok": False, "error": "No se pudo guardar en Supabase"}

    return {
        "ok": True,
        "knowledge_id": resp.data[0]["id"],
        "titulo": registro["title"],
        "autor": registro["autor"],
        "duracion_min": duracion_seg // 60,
        "caracteres_transcript": len(contenido),
        "video_id": video_id,
        "ejecutado": datetime.now(timezone.utc).isoformat(),
    }
