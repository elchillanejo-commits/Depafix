from pydantic import BaseModel
from typing import List
from uuid import UUID

class LoginRequest(BaseModel):
    email: str
    password: str

class CotizacionCreate(BaseModel):
    cliente_final: str
    superficie_m2: float
    partidas: List[dict] # Recibe las partidas en crudo

class CotizacionResponse(BaseModel):
    id_cotizacion: UUID
    resumen_financiero: dict
    pdf_url: str
