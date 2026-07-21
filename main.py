from fastapi import FastAPI, HTTPException
from dotenv import load_dotenv
import os
import sys

# Cargar variables de entorno
load_dotenv()

# reorg 2026-07-19: core/ y src/trading/ movidos fuera de DepaFix
for _p in ("/home/ibar/Proyectos/02_PROCURADOR", "/home/ibar/Proyectos/05_TRADE_CRIPTO"):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# Importamos las rutas centralizadas
from config.settings import DATA_DIR
from core.db_manager import DatabaseManager

app = FastAPI()


@app.post("/trading/ejecutar-cripto")
def ejecutar_pipeline_cripto():
    """Disparador manual del ciclo ingesta+evaluación de TradingLogic (ver
    src/trading/orquestador_cripto.py). Es síncrono y puede tardar si el
    exchange rate-limitea (hay backoff exponencial con reintentos) -- para
    ejecución recurrente real, usar cron contra el script directamente,
    igual que el resto de los agentes del proyecto, no este endpoint."""
    from trading.orquestador_cripto import ejecutar_ciclo
    try:
        resultados = ejecutar_ciclo()
        return {"resultados": resultados}
    except Exception as e:
        print(f"ERROR CRÍTICO en pipeline cripto: {str(e)}", file=sys.stderr)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/clientes")
def listar_clientes():
    try:
        # Ejemplo de uso de la ruta centralizada (si necesitaras leer un JSON local)
        # archivo_datos = DATA_DIR / "clientes.json"
        
        client = DatabaseManager.get_client()
        response = client.table("clientes").select("*").execute()
        return response.data
    except Exception as e:
        print(f"ERROR CRÍTICO: {str(e)}", file=sys.stderr)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
def health():
    return {"status": "ok", "data_path": str(DATA_DIR)}
