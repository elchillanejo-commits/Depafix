"""
seed_knowledge.py — Alimenta a Ikki con videos reales.
"""
import logging
from src.agencia.nutriente import Nutriente
from src.agencia.procesar_conocimiento import ProcesadorIkki

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

def main():
    log.info("Iniciando inyección de conocimiento real...")
    nutriente = Nutriente()
    procesador = ProcesadorIkki()

    # Videos reales con subtítulos garantizados
    videos = [
        ("https://www.youtube.com/watch?v=u4ZoJKF_VuA", "Simon Sinek - Start with Why"),
        ("https://www.youtube.com/watch?v=nU-IIXBWlS4", "Estrategias de Marketing Digital")
    ]

    for url, titulo in videos:
        nutriente.procesar_video(url, titulo)

    procesador.procesar_pendientes()
    procesador.generar_system_prompt()

    print("\n=== NUEVO SYSTEM PROMPT DE IKKI ===")
    with open("src/agencia/prompts/ikki_system.txt", "r") as f:
        print(f.read())
    print("===================================\n")

if __name__ == "__main__":
    main()
