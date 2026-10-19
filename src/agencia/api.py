"""
api.py — Endpoint FastAPI para Agencia Ikki.
Incluye POST para crear y GET para listar campañas.
"""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from src.agencia.motor_ikki import AgenciaIkkiMotor
import os
from supabase import create_client

app = FastAPI(title="Ikki Agency API")
motor = AgenciaIkkiMotor()

class Prospecto(BaseModel):
    cliente_id: str
    rubro: str
    presupuesto_pauta: int

@app.get("/")
def health_check():
    """Ruta para que Railway verifique que el contenedor está vivo."""
    return {"status": "ok", "service": "Ikki Agency API"}

@app.post("/api/v1/simular")
def simular_campana(prospecto: Prospecto):
    try:
        payload = motor.simular_campana_completa(
            {"id": prospecto.cliente_id, "rubro": prospecto.rubro},
            prospecto.presupuesto_pauta
        )
        exito = motor.guardar_en_supabase(payload)
        if not exito:
            raise HTTPException(status_code=500, detail="Error al guardar en Supabase")
        return {"status": "success", "campaña_generada": payload}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/v1/campanas")
def listar_campanas():
    """Devuelve las últimas 10 campañas creadas en Supabase."""
    try:
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        client = create_client(url, key)
        
        # Traemos las últimas 10 campañas, ordenadas por fecha de creación
        result = client.table("campanas_meta").select("*").order("created_at", desc=True).limit(10).execute()
        return {"status": "success", "total": len(result.data), "data": result.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
