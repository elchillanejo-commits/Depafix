from __future__ import annotations

import asyncio
import hashlib
import logging
import math
import os
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from supabase import AsyncClient

from app.core.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/rag", tags=["RAG & Conocimiento"])

RAG_TIMEOUT_SECONDS = float(os.getenv("RAG_TIMEOUT_SECONDS", "10"))
RAG_EMBEDDING_DIMENSIONS = int(os.getenv("RAG_EMBEDDING_DIMENSIONS", "384"))
MAX_EMBEDDING_DIMENSIONS = 4096


class BusquedaRagRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    consulta: str | None = Field(
        default=None,
        min_length=1,
        max_length=4000,
        description=(
            "Texto de consulta. Si no se envía 'embedding', se genera un vector "
            "de prueba determinista (no semántico)."
        ),
    )
    embedding: list[float] | None = Field(
        default=None,
        min_length=1,
        max_length=MAX_EMBEDDING_DIMENSIONS,
        description=(
            f"Embedding precalculado de {RAG_EMBEDDING_DIMENSIONS} dimensiones. "
            "Tiene prioridad sobre 'consulta'."
        ),
    )
    domain: str = Field(
        default="general",
        min_length=1,
        max_length=64,
        description="Filtro de dominio para match_knowledge_v2 (ej. tierra, metal, agua).",
    )
    match_count: int = Field(default=5, ge=1, le=20)

    @field_validator("embedding")
    @classmethod
    def validar_embedding(cls, valor: list[float] | None) -> list[float] | None:
        if valor is None:
            return None
        if len(valor) != RAG_EMBEDDING_DIMENSIONS:
            raise ValueError(
                f"El embedding debe tener exactamente {RAG_EMBEDDING_DIMENSIONS} dimensiones."
            )
        for indice, componente in enumerate(valor):
            if not math.isfinite(componente):
                raise ValueError(f"El componente {indice} del embedding no es finito.")
        return valor

    @model_validator(mode="after")
    def validar_entrada(self) -> "BusquedaRagRequest":
        if self.consulta is None and self.embedding is None:
            raise ValueError("Debes enviar 'consulta' o un 'embedding' precalculado.")
        return self


class BusquedaRagResponse(BaseModel):
    status: Literal["success"] = "success"
    consulta: str | None = None
    embedding_origen: Literal["proporcionado", "prueba_determinista"]
    embedding_dimensiones: int
    domain: str
    match_count: int
    matches: list[dict[str, Any]]


def _generar_embedding_prueba(texto: str, dimensiones: int = RAG_EMBEDDING_DIMENSIONS) -> list[float]:
    """Genera un vector determinista para pruebas. No tiene valor semántico real."""
    if dimensiones <= 0:
        raise ValueError("Las dimensiones del embedding deben ser mayores que cero.")
    semilla = hashlib.sha256(texto.encode("utf-8")).digest()
    valores: list[float] = []
    bloque_num = 0
    while len(valores) < dimensiones:
        bloque = hashlib.sha256(semilla + bloque_num.to_bytes(4, "big")).digest()
        for offset in range(0, len(bloque), 4):
            if len(valores) >= dimensiones:
                break
            entero = int.from_bytes(bloque[offset : offset + 4], "big")
            valores.append((entero / 0xFFFFFFFF) * 2.0 - 1.0)
        bloque_num += 1
    return valores


async def get_db_cliente() -> AsyncClient:
    """Resuelve el cliente async y traduce fallos de configuración a 503."""
    try:
        return await get_db()
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("No se pudo obtener el cliente async de Supabase")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Servicio de base de datos no disponible.",
        ) from exc


@router.post(
    "/buscar",
    response_model=BusquedaRagResponse,
    status_code=status.HTTP_200_OK,
    summary="Búsqueda semántica en knowledge vía match_knowledge_v2",
)
async def buscar_conocimiento(
    payload: BusquedaRagRequest,
    db: AsyncClient = Depends(get_db_cliente),
) -> BusquedaRagResponse:
    if payload.embedding is not None:
        vector = payload.embedding
        origen: Literal["proporcionado", "prueba_determinista"] = "proporcionado"
    elif payload.consulta is not None:
        vector = _generar_embedding_prueba(payload.consulta)
        origen = "prueba_determinista"
    else:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Debes enviar 'consulta' o un 'embedding' precalculado.",
        )

    parametros = {
        "query_embedding": vector,
        "filtro_domain": payload.domain,
        "match_count": payload.match_count,
    }

    try:
        respuesta = await asyncio.wait_for(
            db.rpc("match_knowledge_v2", parametros).execute(),
            timeout=RAG_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError as exc:
        logger.warning("Timeout de match_knowledge_v2 tras %.1fs", RAG_TIMEOUT_SECONDS)
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="La búsqueda RAG excedió el tiempo máximo.",
        ) from exc
    except Exception as exc:
        logger.exception("Error ejecutando match_knowledge_v2")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="No fue posible consultar el servicio RAG.",
        ) from exc

    if not isinstance(respuesta.data, list):
        logger.error(
            "Respuesta inesperada de match_knowledge_v2: %s",
            type(respuesta.data).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Respuesta inválida del servicio RAG.",
        )

    return BusquedaRagResponse(
        consulta=payload.consulta,
        embedding_origen=origen,
        embedding_dimensiones=len(vector),
        domain=payload.domain,
        match_count=payload.match_count,
        matches=respuesta.data,
    )
