import os
import re
import logging
import requests
from datetime import datetime, timezone
from youtube_transcript_api import YouTubeTranscriptApi
from supabase import create_client

logger = logging.getLogger(__name__)

async def youtube_ingest_worker(params: dict) -> dict:
    """Descarga transcript de YouTube y lo guarda en knowledge_items."""
    url = params.get("url")
    tags = params.get("tags", [])
    
    if not url:
        return {"ok": False, "error": "Falta url"}
        
    # 1. Extraer video_id
    video_id_match = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11}).*", url)
    if not video_id_match:
        return {"ok": False, "error": "No se pudo extraer video_id"}
    video_id = video_id_match.group(1)
    
    # 2. Descargar transcript
    try:
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=["es", "en"])
        contenido = " ".join([item["text"] for item in transcript_list])
    except Exception as e:
        return {"ok": False, "error": f"Error obteniendo transcript: {str(e)}"}
        
    # 4. Obtener metadatos con oEmbed
    oembed_url = f"https://www.youtube.com/oembed?url={url}&format=json"
    meta = {}
    try:
        resp = requests.get(oembed_url, timeout=5)
        if resp.status_code == 200:
            meta = resp.json()
    except:
        pass
        
    # 5. Guardar en Supabase
    client = create_client(
        os.getenv("SUPABASE_URL"),
        os.getenv("SUPABASE_SERVICE_ROLE_KEY"),
    )
    
    data = {
        "source": "youtube",
        "url": url,
        "title": meta.get("title", "Unknown"),
        "autor": meta.get("author_name", "Unknown"),
        "contenido": contenido,
        "tags": tags,
        "duracion_seg": 0, # Opcional: calcular a partir de meta si disponible
        "creado_en": datetime.now(timezone.utc).isoformat(),
        "procesado": False
    }
    
    insert = client.table("knowledge_items").insert(data).execute()
    knowledge_id = insert.data[0]["id"]
    
    return {
        "ok": True,
        "knowledge_id": knowledge_id,
        "titulo": data["title"],
        "autor": data["autor"],
        "duracion_min": 0,
        "caracteres_transcript": len(contenido),
        "ejecutado": datetime.now(timezone.utc).isoformat()
    }
