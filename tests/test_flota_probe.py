"""Tests para flota_probe (lógica pura)."""
from __future__ import annotations

from datetime import date, timedelta

from ceo.workers.flota_probe import (
    DIAS_DOC_POR_VENCER,
    FACTOR_RENDIMIENTO_ANORMAL,
    _docs_por_vencer,
    _rendimiento_anormal,
    _service_vencido,
)


def test_constantes():
    assert DIAS_DOC_POR_VENCER == 30
    assert FACTOR_RENDIMIENTO_ANORMAL == 1.25


def test_service_vencido():
    assert _service_vencido({"km_actual": 100, "km_proximo_service": 100}) is True
    assert _service_vencido({"km_actual": 99,  "km_proximo_service": 100}) is False


def test_docs_por_vencer():
    hoy = date.today()
    assert _docs_por_vencer({"documentos_vencen": (hoy + timedelta(days=10)).isoformat()}) is True
    assert _docs_por_vencer({"documentos_vencen": (hoy + timedelta(days=60)).isoformat()}) is False
    assert _docs_por_vencer({}) is False
    assert _docs_por_vencer({"documentos_vencen": None}) is False


def test_rendimiento_sin_viajes():
    v = {"rendimiento_km_l": 3.0}
    assert _rendimiento_anormal(v, []) is None


def test_rendimiento_normal():
    v = {"rendimiento_km_l": 3.0}
    viajes = [{"id": 1, "fecha": "2026-10-01", "km": 100, "litros": 33.0}]
    assert _rendimiento_anormal(v, viajes) is None


def test_rendimiento_anormal():
    v = {"rendimiento_km_l": 3.0}
    viajes = [{"id": 1, "fecha": "2026-10-01", "km": 100, "litros": 50.0}]
    r = _rendimiento_anormal(v, viajes)
    assert r is not None
    assert r["total_outliers"] == 1
    assert r["detalle"][0]["ratio_pct"] > 0
