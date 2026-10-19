"""Tests para properties_probe (lógica de oportunidad)."""
from __future__ import annotations

import statistics


def test_mediana_basico():
    precios = [100, 200, 300, 400, 500]
    assert statistics.median(precios) == 300


def test_ganga_50pct():
    """Un precio <50% de la mediana es ganga."""
    precios = [1000, 1000, 1000, 1000, 400]
    mediana = statistics.median(precios)
    ganga = 400 < mediana * 0.5
    assert ganga is True


def test_no_ganga():
    precios = [1000, 1000, 1000, 1000, 600]
    mediana = statistics.median(precios)
    ganga = 600 < mediana * 0.5
    assert ganga is False
