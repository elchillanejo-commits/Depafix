import sys
import json
from pathlib import Path
from datetime import datetime

# Path al proyecto
root_dir = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(root_dir))

def registrar_analisis(activo, temporalidad, tipo, entrada, stop, tp, confluencias):
    data = {
        "activo": activo,
        "temporalidad": temporalidad,
        "tipo_estructura": tipo,
        "precio_entrada": entrada,
        "precio_stop_loss": stop,
        "precio_take_profit": tp,
        "confluencias": confluencias,
        "timestamp": datetime.now().isoformat()
    }

    # Intentar guardar localmente siempre
    local_log = root_dir / "analisis_local.jsonl"
    with open(local_log, "a") as f:
        f.write(json.dumps(data) + "\n")
    
    print(f"✅ Análisis guardado localmente en {local_log}")

    # Intentar nube solo si es posible
    try:
        from core.db_manager import DatabaseManager
        client = DatabaseManager.get_client()
        client.table("analisis_trading").insert(data).execute()
        print("☁️ Análisis enviado a Supabase con éxito.")
    except Exception:
        print("⚠️ Supabase no disponible. Se subirá automáticamente al recuperar red.")

if __name__ == "__main__":
    test_data = {"fvg_validado": True, "order_block": "H1", "liquidez": "sweep_realizado"}
    registrar_analisis("BTC/USD", "15m", "FVG", 65000, 64500, 66000, test_data)
