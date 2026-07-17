import sys
from pathlib import Path

CORE_PATH = Path(__file__).resolve().parent.parent.parent
if str(CORE_PATH) not in sys.path:
    sys.path.insert(0, str(CORE_PATH))

import pandas as pd
from config.settings import BASE_DIR

def check_health():
    clean_file = BASE_DIR / 'data' / 'inmo_data_clean.csv'
    try:
        df = pd.read_csv(clean_file)
        print("--- REPORTE DE SALUD DEPAFIX ---")
        print(f"Total registros limpios: {len(df)}")
        print(f"Precio promedio: {df['precio'].mean():.2f}")
        print(f"Última actualización: {df['fecha'].max()}")
        print("ESTADO: SISTEMA OPERATIVO Y SALUDABLE")
    except FileNotFoundError:
        print("[ERROR] Archivo no encontrado. Ejecuta primero el pipeline.")

if __name__ == "__main__":
    check_health()
