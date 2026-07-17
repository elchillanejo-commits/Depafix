import sys
from pathlib import Path

# Mismo patrón que src/trading/orquestador_cripto.py: hay que poner la raíz
# del repo en sys.path ANTES de poder importar "config" -- si este archivo
# se corre como script suelto (python3 src/agents/inmo_scrapper.py), Python
# solo agrega src/agents/ a sys.path, no la raíz del repo.
CORE_PATH = Path(__file__).resolve().parent.parent.parent
if str(CORE_PATH) not in sys.path:
    sys.path.insert(0, str(CORE_PATH))

import requests
from bs4 import BeautifulSoup
import csv
from datetime import datetime
from config.settings import BASE_DIR

def run_scrapper():
    # URL de prueba (ejemplo de sitio inmobiliario)
    url = "https://www.portalinmobiliario.com/venta/departamento"
    print(f"[AGENTE] Iniciando escaneo en: {url}")
    
    # Simulación de extracción (Aquí insertarías la lógica real del sitio)
    # datos = soup.find_all(...) 
    data = {"titulo": "Depto Centro", "precio": 3500, "fecha": str(datetime.now())}
    
    output_file = BASE_DIR / 'data' / 'inmo_data.csv'
    escribir_header = not output_file.exists()
    with open(output_file, 'a', newline='') as f:
        writer = csv.writer(f)
        if escribir_header:
            writer.writerow(['titulo', 'precio', 'fecha'])
        writer.writerow([data['titulo'], data['precio'], data['fecha']])
    
    print(f"[OK] Datos guardados en {output_file}")

if __name__ == "__main__":
    run_scrapper()
