import sys
import time
for _p in ("/home/ibar/Proyectos/02_PROCURADOR", "/home/ibar/Proyectos/05_TRADE_CRIPTO"):
    if _p not in sys.path:
        sys.path.insert(0, _p)
from core.db_manager import db
from data_pipeline import PipelineVelas

def monitor_sol():
    """Monitorea SOL/USDT y alerta cuando toca niveles clave."""
    pipeline = PipelineVelas()
    velas = pipeline.obtener_velas('SOL/USDT', '4h', 5)
    if not velas:
        return
    
    precio_actual = velas[-1]['close']
    soporte = 75.45
    resistencia = 78.30
    
    if precio_actual <= soporte * 1.01:
        print(f"🔴 SOL/USDT cerca de soporte: ${precio_actual}")
    elif precio_actual >= resistencia * 0.99:
        print(f"🟢 SOL/USDT cerca de resistencia: ${precio_actual}")
    else:
        print(f"📊 SOL/USDT en rango: ${precio_actual}")

if __name__ == "__main__":
    monitor_sol()
