"""
nutriente.py — Ingesta de conocimiento desde YouTube (Día 8).
Soporte para youtube-transcript-api >= 1.0.
"""
import os
import json
import logging
from youtube_transcript_api import YouTubeTranscriptApi
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()
log = logging.getLogger(__name__)

class Nutriente:
    def __init__(self):
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        if not url or not key:
            raise ValueError("Faltan credenciales de Supabase en .env")
        self.client = create_client(url, key)
        self.ytt_api = YouTubeTranscriptApi() # Instancia nueva para v1.x

    def extraer_id_video(self, url: str) -> str:
        if "v=" in url:
            return url.split("v=")[1].split("&")[0]
        elif "youtu.be/" in url:
            return url.split("youtu.be/")[1].split("?")[0]
        return url

    def procesar_video(self, url: str, titulo: str) -> bool:
        video_id = self.extraer_id_video(url)
        log.info(f"Procesando video: {video_id} - {titulo}")

        try:
            # 1. Descargar transcripción (Método actualizado v1.x)
            transcript_list = self.ytt_api.fetch(video_id, languages=['es', 'en'])
            # En v1.x se usa .text en lugar de t['text']
            texto_completo = " ".join([t.text for t in transcript_list])
            
            # 2. Guardar en Supabase
            payload = {
                "fuente": "youtube",
                "url": url,
                "titulo": titulo,
                "contenido": texto_completo,
                "metadata": {"video_id": video_id}
            }
            
            result = self.client.table("knowledge_entries").insert(payload).execute()
            log.info(f"✅ Guardado en DB con ID: {result.data[0]['id']}")
            return True
            
        except Exception as e:
            log.error(f"❌ Error con el video {video_id}: {e}")
            return False

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    nutriente = Nutriente()
    url_test = "https://www.youtube.com/watch?v=dQw4w9WgXcQ" 
    titulo_test = "Test de Ingesta de Conocimiento"
    nutriente.procesar_video(url_test, titulo_test)
