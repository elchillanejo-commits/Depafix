import os
from pathlib import Path

# La raíz del proyecto es donde está este archivo (subiendo un nivel desde 'config/')
BASE_DIR = Path(__file__).resolve().parent.parent

# Rutas centralizadas
DATA_DIR = BASE_DIR / "data"
LOGS_DIR = BASE_DIR / "logs"
MODELS_DIR = BASE_DIR / "models"

# Crear carpetas si no existen
for folder in [DATA_DIR, LOGS_DIR, MODELS_DIR]:
    folder.mkdir(exist_ok=True)

def get_path(relative_path: str):
    return BASE_DIR / relative_path
