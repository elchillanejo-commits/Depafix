import os
import json
import logging
from datetime import datetime
from youtube_transcript_api import YouTubeTranscriptApi
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()
log = logging.getLogger(__name__)

class Nutriente:
    def __init__(self):
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        self.client = create_client(url, key) if url and key else None
        self.ytt_api = YouTubeTranscriptApi()
        
        # Carpeta local para el Cerebro
        self.local_dir = "data/knowledge_base"
        os.makedirs(self.local_dir, exist_ok=True)

    def extraer_id_video(self, url: str) -> str:
        if "v=" in url: return url.split("v=")[1].split("&")[0]
        elif "youtu.be/" in url: return url.split("youtu.be/")[1].split("?")[0]
        return url

    def procesar_video(self, url: str, titulo: str) -> bool:
        video_id = self.extraer_id_video(url)
        log.info(f"Procesando video: {video_id} - {titulo}")

        try:
            # 1. Descargar transcripción
            transcript_list = self.ytt_api.fetch(video_id, languages=['es', 'en'])
            texto_completo = " ".join([t.text for t in transcript_list])
            
            payload = {
                "fuente": "youtube",
                "url": url,
                "titulo": titulo,
                "contenido": texto_completo,
                "metadata": {"video_id": video_id, "fecha_local": datetime.now().isoformat()}
            }
            
            # 2. Guardar en LOCAL (JSON)
            local_path = os.path.join(self.local_dir, f"{video_id}.json")
            with open(local_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            log.info(f"✅ Guardado localmente en: {local_path}")

            # 3. Guardar en SUPABASE (Nube)
            if self.client:
                self.client.table("knowledge_entries").insert(payload).execute()
                log.info(f"✅ Guardado en Supabase (Nube)")
                
            return True
            
        except Exception as e:
            log.error(f"❌ Error con el video {video_id}: {e}")
            return False

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    nutriente = Nutriente()
    # Probamos con un video de marketing
    nutriente.procesar_video("https://www.youtube.com/watch?v=u4ZoJKF_VuA", "Simon Sinek - Start with Why")
