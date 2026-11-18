import os
from typing import Any, Dict, List
from fastapi import APIRouter, HTTPException, status
import httpx
from pydantic import BaseModel
from supabase import Client, create_client

router = APIRouter(prefix="/api/v1/proveedores", tags=["Scraper Alibaba - DepaFix"])

ALIBABA_SCRAPER_BASE_URL = os.environ.get("ALIBABA_SCRAPER_URL", "http://localhost:8000")

def get_supabase() -> Client:
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY")
    if not url or not key:
        raise HTTPException(status_code=500, detail="Faltan credenciales de Supabase.")
    return create_client(url, key)

class SearchRequest(BaseModel):
    producto: str

@router.post("/buscar", status_code=201)
async def buscar_e_insertar_proveedores(payload: SearchRequest):
    producto = payload.producto
    scraper_url = f"{ALIBABA_SCRAPER_BASE_URL}/products/search"

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(scraper_url, params={"query": producto})
            if response.status_code != 200:
                raise HTTPException(status_code=502, detail=f"Scraper respondió {response.status_code}")
            data = response.json()
    except httpx.RequestError as exc:
        raise HTTPException(status_code=503, detail=f"No se pudo conectar al scraper: {str(exc)}")

    productos_lista = data if isinstance(data, list) else data.get("products", data.get("results", []))
    if not productos_lista:
        raise HTTPException(status_code=404, detail=f"Sin resultados para: '{producto}'")

    proveedores_a_insertar: List[Dict[str, Any]] = []
    for item in productos_lista[:5]:
        proveedor_info = item.get("supplier", {})
        if isinstance(proveedor_info, dict):
            nombre_prov = proveedor_info.get("name", "Proveedor Alibaba Desconocido")
            years_alibaba = proveedor_info.get("years_on_alibaba", "N/A")
            country_code = proveedor_info.get("country_code", "CN")
            contacto_prov = f"Años en Alibaba: {years_alibaba}, País: {country_code}"
        else:
            nombre_prov = str(proveedor_info) if proveedor_info else "Proveedor Alibaba"
            contacto_prov = "N/A"

        precio_val = item.get("price", {})
        if isinstance(precio_val, dict):
            precio_unitario = precio_val.get("min", 0.0)
        else:
            try:
                precio_unitario = float(precio_val)
            except (TypeError, ValueError):
                precio_unitario = 0.0

        registro = {
            "nombre": nombre_prov,
            "contacto": contacto_prov,
            "productos": [item.get("title", producto)],
            "precios": {"unitario_usd": precio_unitario, "rango": item.get("price")},
            "plazo_entrega_dias": 15,
            "estado": "referencia"
        }
        proveedores_a_insertar.append(registro)

    supabase = get_supabase()
    try:
        db_response = supabase.table("proveedores").insert(proveedores_a_insertar).execute()
        return {
            "status": "success",
            "message": f"Se insertaron {len(proveedores_a_insertar)} proveedores.",
            "proveedores_insertados": db_response.data
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error al insertar: {str(e)}")
