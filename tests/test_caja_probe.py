"""Tests para caja_probe (lógica pura, sin client)."""
from __future__ import annotations

from decimal import Decimal

from ceo.workers.caja_probe import (
    UF_REF_2026_CLP,
    UMBRAL_CONCENTRACION,
    UMBRAL_CUADRE_CLP,
    UMBRAL_DESVIACION,
    _calcular_cuadre_diario,
    _detectar_concentracion,
    _detectar_desviaciones_serviu,
)


def test_constantes():
    assert float(UF_REF_2026_CLP) == 39779.29
    assert UMBRAL_CUADRE_CLP == 100_000
    assert UMBRAL_DESVIACION == 0.30
    assert UMBRAL_CONCENTRACION == 0.60


def test_cuadre_vacio():
    assert _calcular_cuadre_diario([]) == {}


def test_cuadre_un_dia():
    movs = [
        {"fecha": "2026-10-09", "tipo": "ingreso", "monto_clp": 1000},
        {"fecha": "2026-10-09", "tipo": "egreso",  "monto_clp":  300},
    ]
    r = _calcular_cuadre_diario(movs)
    assert r["2026-10-09"] == 700


def test_cuadre_varios_dias():
    movs = [
        {"fecha": "2026-10-08", "tipo": "ingreso", "monto_clp": 5000},
        {"fecha": "2026-10-09", "tipo": "egreso",  "monto_clp": 2000},
    ]
    r = _calcular_cuadre_diario(movs)
    assert r["2026-10-08"] == 5000
    assert r["2026-10-09"] == -2000


def test_concentracion_sin_egresos():
    assert _detectar_concentracion([]) is None


def test_concentracion_baja():
    movs = [
        {"tipo": "egreso", "monto_clp": 100, "categoria": "A"},
        {"tipo": "egreso", "monto_clp": 100, "categoria": "B"},
    ]
    assert _detectar_concentracion(movs) is None


def test_concentracion_alta():
    movs = [
        {"tipo": "egreso", "monto_clp": 900, "categoria": "A"},
        {"tipo": "egreso", "monto_clp": 100, "categoria": "B"},
    ]
    r = _detectar_concentracion(movs)
    assert r is not None
    assert r["categoria"] == "A"
    assert r["pct"] == 90.0


def test_desviaciones_vacio():
    assert _detectar_desviaciones_serviu([], {}) == []


def test_desviacion_detectada():
    movs = [{"id": 1, "tipo": "egreso", "monto_clp": 300000,
             "codigo_serviu": "C-1", "concepto": "test"}]
    precios = {"C-1": Decimal("1.0")}  # 1 UF = ~$39.779
    r = _detectar_desviaciones_serviu(movs, precios)
    assert len(r) == 1
    assert r[0]["pct"] > 100  # 300k vs 39k = 657% de desviación
