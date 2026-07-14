from fastapi import FastAPI, HTTPException
from dotenv import load_dotenv
import os
import sys

# Cargar variables de entorno
load_dotenv()

from core.db_manager import DatabaseManager

app = FastAPI()

@app.get("/api/clientes")
def listar_clientes():
    try:
        client = DatabaseManager.get_client()
        response = client.table("clientes").select("*").execute()
        return response.data
    except Exception as e:
        # Esto imprimirá el error real en la consola donde ejecutes uvicorn
        print(f"ERROR CRÍTICO: {str(e)}", file=sys.stderr)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
def health():
    return {"status": "ok"}
