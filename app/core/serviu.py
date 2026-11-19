"""Capa de precios oficiales SERVIU para el Módulo 1 (Tierra).

Toda la aritmética usa Decimal con redondeo HALF_UP para evitar la pérdida
de centavos del `int(total * 0.19)` del motor anterior. Los precios se
validan contra límites de cordura porque el YAML fue contaminado por el
extractor de Excel (ver BUG-024).
"""

from __future__ import annotations

import math
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

RUTA_YAML = Path(__file__).resolve().parents[2] / "serviu_precios.yml"
IVA = Decimal("0.19")
CENTAVO = Decimal("0.01")
PRECIO_MIN = Decimal("1")
PRECIO_MAX = Decimal("50000000")


class PartidaNoEncontrada(ValueError):
    pass


class PrecioNoConfiable(ValueError):
    pass


@lru_cache(maxsize=1)
def cargar_partidas() -> dict[str, dict[str, Any]]:
    with RUTA_YAML.open("r", encoding="utf-8") as archivo:
        datos = yaml.safe_load(archivo) or {}

    partidas: dict[str, dict[str, Any]] = {}
    for fila in datos.get("partidas", []):
        codigo = str(fila.get("codigo", "")).strip()
        if codigo:
            partidas[codigo] = fila
    return partidas


def validar_precio(valor: Any, codigo: str) -> Decimal:
    if isinstance(valor, bool) or valor is None:
        raise PrecioNoConfiable(f"{codigo}: precio ausente o inválido")
    try:
        numero = float(valor)
    except (TypeError, ValueError) as exc:
        raise PrecioNoConfiable(f"{codigo}: precio no numérico") from exc
    if not math.isfinite(numero):
        raise PrecioNoConfiable(f"{codigo}: precio no finito (nan/inf)")

    precio = Decimal(str(valor))
    if not (PRECIO_MIN <= precio <= PRECIO_MAX):
        raise PrecioNoConfiable(
            f"{codigo}: precio {precio} fuera de rango "
            f"[{PRECIO_MIN}, {PRECIO_MAX}] — dato del extractor corrupto"
        )
    return precio


def obtener_partida(codigo: str) -> dict[str, Any]:
    partida = cargar_partidas().get(str(codigo).strip())
    if partida is None:
        raise PartidaNoEncontrada(f"Código {codigo} no existe en serviu_precios.yml")
    validar_precio(partida.get("precio_unitario"), codigo)
    return partida


def calcular(codigo: str, magnitud: float | Decimal, comuna: str = "") -> dict[str, Any]:
    """Resuelve una partida SERVIU y calcula neto, IVA y total con centavos."""
    partida = obtener_partida(codigo)
    precio_unitario = validar_precio(partida.get("precio_unitario"), codigo)

    try:
        cantidad = Decimal(str(magnitud))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"Magnitud inválida: {magnitud!r}") from exc
    if not cantidad.is_finite() or cantidad <= 0:
        raise ValueError("La magnitud debe ser un número positivo")

    total_neto = (precio_unitario * cantidad).quantize(CENTAVO, rounding=ROUND_HALF_UP)
    iva = (total_neto * IVA).quantize(CENTAVO, rounding=ROUND_HALF_UP)
    total_final = total_neto + iva

    return {
        "codigo": str(codigo).strip(),
        "nombre": partida.get("nombre", ""),
        "unidad": partida.get("unidad", "un"),
        "comuna": comuna,
        "magnitud": float(cantidad),
        "precio_unitario": float(precio_unitario),
        "total_neto": float(total_neto),
        "iva": float(iva),
        "total_final": float(total_final),
    }
