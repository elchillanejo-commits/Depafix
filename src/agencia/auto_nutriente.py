import time
import logging
from src.agencia.nutriente import Nutriente
from src.agencia.local_brain import construir_contexto_maestro

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

# URLs reales de YouTube proporcionadas (Marketing, Meta Ads, Google Ads)
YOUTUBE_URLS = [
    "https://youtu.be/n7MRQ0Fyl_k",
    "https://youtu.be/XntzJv0xjKQ",
    "https://youtu.be/N-A28JFhRwI",
    "https://youtu.be/yYqX5e9Zl8E",
    "https://youtu.be/Age_oMUZptQ",
    "https://youtu.be/WMIsSRqm5Oo",
    "https://youtu.be/cAjYEO6Tpp0",
    "https://youtu.be/wr3L7JMADUk"
]

def ejecutar_pipeline():
    log.info("Iniciando rutina de alimentación automática (Auto-Nutriente)...")
    nutriente = Nutriente()
    
    exitos = 0
    fallos = 0

    for url in YOUTUBE_URLS:
        log.info(f"Procesando: {url}")
        # Evaluamos el retorno booleano de la función
        resultado = nutriente.procesar_video(url, "Video de Marketing")
        
        if resultado:
            exitos += 1
        else:
            fallos += 1
        
        # Rate limiting para evitar bloqueos por parte de YouTube
        log.info("Esperando 5 segundos antes de la siguiente descarga...")
        time.sleep(5)

    # Fase de consolidación del conocimiento
    log.info("--- Fase de Consolidación ---")
    log.info("Reconstruyendo 'contexto_maestro.txt'...")
    try:
        construir_contexto_maestro()
        log.info("Contexto maestro actualizado correctamente.")
    except Exception as e:
        log.error(f"Error al reconstruir el cerebro local: {e}")

    # Resumen final
    log.info("========================================")
    log.info("RESUMEN DE EJECUCIÓN")
    log.info(f"Total procesados: {len(YOUTUBE_URLS)}")
    log.info(f"Éxitos reales: {exitos}")
    log.info(f"Fallos: {fallos}")
    log.info("========================================")

if __name__ == "__main__":
    ejecutar_pipeline()
