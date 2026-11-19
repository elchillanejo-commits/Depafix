import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import AliasChoices, BaseModel, ConfigDict, Field, model_validator
from supabase import AsyncClient
from app.core.database import get_db
from app.core.serviu import PartidaNoEncontrada, PrecioNoConfiable, calcular

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/cotizaciones", tags=["Cotizaciones"])


class ItemPresupuesto(BaseModel):
    desc: str = Field(..., min_length=1)
    precio: float = Field(..., gt=0)


class PartidaServiu(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    codigo: str = Field(
        ..., min_length=1, validation_alias=AliasChoices("codigo", "sku")
    )
    magnitud: float | None = Field(default=None, gt=0)


class PresupuestoCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, populate_by_name=True)

    direccion: str | None = Field(default=None, min_length=5)
    comuna: str | None = Field(default=None, min_length=2)
    items: List[ItemPresupuesto] | None = None
    total_neto: float | None = Field(default=None, gt=0)
    partidas: List[PartidaServiu] | None = None
    magnitud: float | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def validar_contrato(self) -> "PresupuestoCreate":
        es_serviu = bool(self.comuna and self.partidas and self.magnitud)
        es_legado = bool(self.direccion and self.items and self.total_neto)
        if not es_serviu and not es_legado:
            raise ValueError(
                "Enviar (comuna, partidas, magnitud) o "
                "(direccion, items, total_neto)."
            )
        return self


@router.post("/", status_code=status.HTTP_201_CREATED)
async def crear_cotizacion(payload: PresupuestoCreate, db: AsyncClient = Depends(get_db)):
    resumen: dict | None = None

    try:
        if payload.partidas:
            try:
                calculos = [
                    calcular(
                        partida.codigo,
                        partida.magnitud or payload.magnitud,
                        payload.comuna,
                    )
                    for partida in payload.partidas
                ]
            except (PartidaNoEncontrada, PrecioNoConfiable, ValueError) as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc

            direccion = payload.comuna
            total_neto = round(sum(c["total_neto"] for c in calculos), 2)
            iva = round(sum(c["iva"] for c in calculos), 2)
            total_final = round(total_neto + iva, 2)
            items = [
                {
                    "desc": (
                        f"{c['codigo']} - {c['nombre']} "
                        f"({c['magnitud']:g} {c['unidad']}) "
                        f"@ ${c['precio_unitario']:,.0f}"
                    ),
                    "precio": c["total_neto"],
                }
                for c in calculos
            ]
            resumen = {
                "subtotal_venta_neto": total_neto,
                "monto_iva": iva,
                "total_presupuesto_bruto": total_final,
                "fuente_precios": "serviu_precios.yml",
            }
        else:
            direccion = payload.direccion
            total_neto = payload.total_neto
            items = [item.model_dump() for item in payload.items]
            logger.warning(
                "Cotización con precios aportados por el cliente (sin validar SERVIU)."
            )

        datos = {"direccion": direccion, "total_neto": total_neto, "items": items}
        response = await db.table("cotizaciones").insert(datos).execute()
        if not response.data:
            raise HTTPException(status_code=400, detail="No se pudo guardar.")

        resultado = dict(response.data[0])
        if resumen:
            resultado["resumen_financiero"] = resumen
        return {"status": "success", "data": resultado}
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("No se pudo crear la cotización")
        raise HTTPException(
            status_code=500, detail=f"Error al crear cotización ({type(exc).__name__})."
        ) from exc


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
