"""API DTE de DepaFix: recibe y valida la estructura de una factura electrónica.

Contrato de datos: skill @depafix-dte (.opencode/skills/depafix-dte.md)
El esquema es estricto: campos extra, RUT mal formados o totales incoherentes
rechazan la factura con 422.
"""

import re
from typing import List

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# Tipos de documento tributario electronicos admitidos (SII)
TIPOS_DOCUMENTO = {
    33: "Factura Electronica",
    34: "Factura Exenta",
    41: "Boleta Electronica",
    46: "Nota de Debito",
    52: "Guia de Despacho",
    56: "Nota de Venta",
    61: "Nota de Credito",
}

TOLERANCIA_TOTALES = 1.0  # pesos

app = FastAPI(title="DepaFix DTE API")


def _dv_valido(rut_normalizado: str) -> bool:
    """Valida el digito verificador con el algoritmo modulo 11 del SII."""
    cuerpo, dv = rut_normalizado.split("-")
    cuerpo = cuerpo.replace(".", "")
    suma, multiplicador = 0, 2
    for digito in reversed(cuerpo):
        suma += int(digito) * multiplicador
        multiplicador = 2 if multiplicador == 7 else multiplicador + 1
    resto = suma % 11
    calculado = 11 - resto
    if calculado == 11:
        esperado = "0"
    elif calculado == 10:
        esperado = "K"
    else:
        esperado = str(calculado)
    return esperado == dv


def _normalizar_rut(valor: str) -> str:
    """Acepta RUT con o sin puntos y lo devuelve en formato XX.XXX.XXX-X."""
    limpio = re.sub(r"[^0-9Kk]", "", (valor or "").strip())
    if not 8 <= len(limpio) <= 9:
        raise ValueError("RUT invalido: se esperaba XX.XXX.XXX-X")
    cuerpo, dv = limpio[:-1], limpio[-1].upper()
    normalizado = f"{cuerpo[:-6]}.{cuerpo[-6:-3]}.{cuerpo[-3:]}-{dv}"
    if not _dv_valido(normalizado):
        raise ValueError(f"RUT invalido: digito verificador incorrecto ({normalizado})")
    return normalizado


class Parte(BaseModel):
    """Emisor o receptor del DTE."""

    rut: str
    razon_social: str = Field(min_length=1, max_length=200)

    @field_validator("rut")
    @classmethod
    def validar_rut(cls, valor: str) -> str:
        return _normalizar_rut(valor)


class Totales(BaseModel):
    neto: float = Field(ge=0)
    iva: float = Field(ge=0)
    total: float = Field(ge=0)

    @model_validator(mode="after")
    def coherencia(self) -> "Totales":
        if abs((self.neto + self.iva) - self.total) > TOLERANCIA_TOTALES:
            raise ValueError(
                f"total ({self.total}) debe ser neto ({self.neto}) + iva ({self.iva})"
            )
        return self


class Item(BaseModel):
    codigo: str = Field(min_length=1)
    descripcion: str = Field(min_length=1, max_length=500)
    cantidad: float = Field(gt=0)
    precio_unitario: float = Field(ge=0)


class FacturaElectronica(BaseModel):
    """Contrato de datos del skill @depafix-dte (extra='forbid')."""

    model_config = ConfigDict(extra="forbid")

    dte_id: str = Field(min_length=1, max_length=64)
    tipo_documento: int
    emisor: Parte
    receptor: Parte
    totales: Totales
    items: List[Item] = Field(min_length=1)

    @field_validator("tipo_documento")
    @classmethod
    def tipo_valido(cls, valor: int) -> int:
        if valor not in TIPOS_DOCUMENTO:
            admitidos = ", ".join(str(t) for t in sorted(TIPOS_DOCUMENTO))
            raise ValueError(f"tipo_documento {valor} no admitido (usa: {admitidos})")
        return valor

    @model_validator(mode="after")
    def items_cuadran_con_neto(self) -> "FacturaElectronica":
        suma_items = sum(i.cantidad * i.precio_unitario for i in self.items)
        tolerancia = len(self.items) * TOLERANCIA_TOTALES + TOLERANCIA_TOTALES
        if abs(suma_items - self.totales.neto) > tolerancia:
            raise ValueError(
                f"la suma de los items ({suma_items:.2f}) no coincide "
                f"con el neto ({self.totales.neto:.2f})"
            )
        return self


@app.exception_handler(RequestValidationError)
async def estructura_invalida(request: Request, exc: RequestValidationError):
    errores = []
    for error in exc.errors():
        ubicacion = ".".join(str(p) for p in error["loc"] if p != "body")
        errores.append(f"{ubicacion}: {error['msg']}")
    return JSONResponse(
        status_code=422,
        content={
            "success": False,
            "error": "Estructura de factura electronica invalida",
            "detail": errores,
        },
    )


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/dte/tipos")
def tipos_documento():
    return JSONResponse(
        status_code=200,
        content={"success": True, "data": TIPOS_DOCUMENTO},
    )


@app.post("/api/dte", status_code=201)
def recibir_dte(factura: FacturaElectronica):
    """Recibe una factura electronica y devuelve la estructura ya validada."""
    suma_items = sum(i.cantidad * i.precio_unitario for i in factura.items)
    return JSONResponse(
        status_code=201,
        content={
            "success": True,
            "data": {
                "dte_id": factura.dte_id,
                "tipo_documento": factura.tipo_documento,
                "tipo": TIPOS_DOCUMENTO[factura.tipo_documento],
                "emisor": factura.emisor.model_dump(),
                "receptor": factura.receptor.model_dump(),
                "totales": factura.totales.model_dump(),
                "cantidad_items": len(factura.items),
                "suma_items": round(suma_items, 2),
                "estado": "validada",
            },
        },
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8011)
