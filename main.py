from fastapi import FastAPI, HTTPException
from dotenv import load_dotenv
import os
import sys

# Cargar variables de entorno
load_dotenv()

# Importamos las rutas centralizadas
from config.settings import DATA_DIR
from core.db_manager import DatabaseManager

app = FastAPI()

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
