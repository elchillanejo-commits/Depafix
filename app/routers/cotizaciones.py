import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, ConfigDict
from supabase import AsyncClient
from app.core.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/cotizaciones", tags=["Cotizaciones"])

class ItemPresupuesto(BaseModel):
    desc: str = Field(..., min_length=1)
    precio: float = Field(..., gt=0)

class PresupuestoCreate(BaseModel):
    direccion: str = Field(..., min_length=5)
    items: List[ItemPresupuesto] = Field(..., min_length=1)
    total_neto: float = Field(..., gt=0)
    model_config = ConfigDict(str_strip_whitespace=True)

@router.post("/", status_code=status.HTTP_201_CREATED)
async def crear_cotizacion(payload: PresupuestoCreate, db: AsyncClient = Depends(get_db)):
    try:
        datos = {
            "direccion": payload.direccion,
            "total_neto": payload.total_neto,
            "items": [item.model_dump() for item in payload.items]
        }
        response = await db.table("cotizaciones").insert(datos).execute()
        if not response.data:
            raise HTTPException(status_code=400, detail="No se pudo guardar.")
        return {"status": "success", "data": response.data[0]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@router.get("/")
async def listar_cotizaciones(db: AsyncClient = Depends(get_db)):
    try:
        response = (
            await db.table("cotizaciones")
            .select("*")
            .order("created_at", desc=True)
            .limit(50)
            .execute()
        )
        return {"status": "success", "data": response.data or []}
    except Exception as exc:
        logger.warning("No se pudieron listar cotizaciones: %s", type(exc).__name__)
        raise HTTPException(
            status_code=500,
            detail=f"Error al listar cotizaciones ({type(exc).__name__}).",
        ) from exc
