"""Tests para flota_probe (lógica pura)."""
from __future__ import annotations

from datetime import date, timedelta

from ceo.workers.flota_probe import (
    DIAS_ALERTA_DOC,
    KM_ALERTA_SERVICE,
    UMBRAL_RENDIMIENTO,
    _check_documentos,
    _check_rendimiento,
    _check_service,
)


def test_constantes():
    assert KM_ALERTA_SERVICE == 500
    assert DIAS_ALERTA_DOC == 30
    assert UMBRAL_RENDIMIENTO == 0.80


def test_service_vencido():
    r = _check_service({"km_actual": 100, "km_proximo_service": 100})
    assert r is not None
    assert r["tipo"] == "service"
    assert r["falta_km"] == 0

    r = _check_service({"km_actual": 100, "km_proximo_service": 600})
    assert r is not None
    assert r["falta_km"] == KM_ALERTA_SERVICE

    assert _check_service({"km_actual": 100, "km_proximo_service": 601}) is None


def test_docs_por_vencer():
    hoy = date.today()
    r = _check_documentos(
        {"documentos_vencen": (hoy + timedelta(days=10)).isoformat()}, hoy
    )
    assert r is not None
    assert r["tipo"] == "documentos"
    assert r["dias_restantes"] == 10

    assert _check_documentos(
        {"documentos_vencen": (hoy + timedelta(days=60)).isoformat()}, hoy
    ) is None
    assert _check_documentos({}, hoy) is None
    assert _check_documentos({"documentos_vencen": None}, hoy) is None


def test_rendimiento_sin_viajes():
    v = {"patente": "ABC123", "rendimiento_km_l": 3.0}
    assert _check_rendimiento(v, []) is None


def test_rendimiento_normal():
    v = {"patente": "ABC123", "rendimiento_km_l": 3.0}
    viajes = [
        {"patente": "ABC123", "fecha": "2026-10-01", "km": 100, "litros": 33.0}
    ]
    assert _check_rendimiento(v, viajes) is None


def test_rendimiento_anormal():
    v = {"patente": "ABC123", "rendimiento_km_l": 3.0}
    viajes = [
        {"patente": "ABC123", "fecha": "2026-10-01", "km": 100, "litros": 50.0}
    ]
    r = _check_rendimiento(v, viajes)
    assert r is not None
    assert r["tipo"] == "rendimiento"
    assert r["rendimiento_real"] == 2.0
    assert r["ratio"] == 0.67
    assert r["ratio"] < UMBRAL_RENDIMIENTO
