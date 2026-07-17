import subprocess
import sys
from pathlib import Path

CORE_PATH = Path(__file__).resolve().parent.parent
if str(CORE_PATH) not in sys.path:
    sys.path.insert(0, str(CORE_PATH))

from config.settings import BASE_DIR

def ejecutar_pipeline():
    print("--- INICIANDO PIPELINE DEPAFIX ---")
    
    # 1. Ejecutar Scraper
    subprocess.run(["python3", str(BASE_DIR / 'src' / 'agents' / 'inmo_scrapper.py')])
    
    # 2. Ejecutar Calidad
    subprocess.run(["python3", str(BASE_DIR / 'src' / 'analytics' / 'quality_gate.py')])
    
    # 3. Mostrar Reporte de Salud
    subprocess.run(["python3", str(BASE_DIR / 'src' / 'analytics' / 'health_check.py')])
    
    print("--- PIPELINE FINALIZADO ---")

if __name__ == "__main__":
    ejecutar_pipeline()
