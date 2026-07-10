from __future__ import annotations
from pydantic import BaseModel, Field, field_validator
from enum import Enum

# ---------- Value Objects ----------
class MetrosCuadrados(BaseModel):
    valor: float = Field(..., gt=0)
    def __add__(self, other): return MetrosCuadrados(valor=self.valor + other.valor)
    def __mul__(self, factor): return MetrosCuadrados(valor=self.valor * factor)

class Dinero(BaseModel):
    monto: float = Field(..., ge=0)
    moneda: str = "CLP"
    @field_validator('moneda')
    @classmethod
    def moneda_valida(cls, v):
        if v not in ['CLP','UF']: raise ValueError('Moneda inválida')
        return v
    def __mul__(self, factor): return Dinero(monto=self.monto * factor, moneda=self.moneda)

class Confianza(BaseModel):
    valor: float = Field(..., ge=0.0, le=1.0)

class DuracionEstimada(BaseModel):
    dias: int = Field(..., ge=1)
    confianza: Confianza

class EstadoObra(str, Enum):
    PENDIENTE = "pendiente"
    EN_PROGRESO = "en_progreso"
    FINALIZADA = "finalizada"
