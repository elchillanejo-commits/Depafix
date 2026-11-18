import os
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, EmailStr
from supabase import Client, create_client

router = APIRouter(prefix="/api/v1", tags=["CRM - DepaFix"])

def get_supabase() -> Client:
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise HTTPException(status_code=500, detail="Faltan credenciales de Supabase.")
    return create_client(url, key)

class ProveedorCreate(BaseModel):
    nombre: str
    contacto: str
    productos: List[str]
    precios: Dict[str, float]
    plazo_entrega: int

class ClienteCreate(BaseModel):
    nombre: str
    email: EmailStr
    telefono: str
    direccion: str
    comuna: str

@router.post("/proveedores", status_code=201)
def crear_proveedor(proveedor: ProveedorCreate):
    supabase = get_supabase()
    try:
        response = supabase.table("proveedores").insert(proveedor.dict()).execute()
        return {"status": "success", "message": "Proveedor creado", "data": response.data}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error: {str(e)}")

@router.get("/proveedores")
def listar_proveedores():
    supabase = get_supabase()
    try:
        response = supabase.table("proveedores").select("*").execute()
        return {"status": "success", "count": len(response.data), "data": response.data}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error: {str(e)}")

@router.post("/clientes", status_code=201)
def crear_cliente(cliente: ClienteCreate):
    supabase = get_supabase()
    try:
        response = supabase.table("clientes").insert(cliente.dict()).execute()
        return {"status": "success", "message": "Cliente creado", "data": response.data}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error: {str(e)}")

@router.get("/clientes/{cliente_id}")
def obtener_cliente(cliente_id: str):
    supabase = get_supabase()
    try:
        res = supabase.table("clientes").select("*").eq("id", cliente_id).execute()
        if not res.data:
            raise HTTPException(status_code=404, detail="Cliente no encontrado")
        return {"status": "success", "data": res.data[0]}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error: {str(e)}")
