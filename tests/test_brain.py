"""Tests para estrategia e indicadores."""
import pytest
import numpy as np

from indicators.technical import IndicadoresTecnicos
from strategy.regime import detectar_regimen
from strategy.multi_timeframe import score_multi_timeframe, evaluar_tendencia_tf
from strategy.sizing import calcular_tamano_posicion
from strategy.exits import calcular_niveles_salida


def test_rsi_calculation():
    ind = IndicadoresTecnicos()
    closes = list(range(100, 130))
    candles = [
        {"timestamp": f"2024-01-01T{i:02d}:00:00", "open": c, "high": c + 1, "low": c - 1, "close": c, "volume": 1000}
        for i, c in enumerate(closes)
    ]
    result = ind.update("BTC/USD", "1h", candles)
    assert "rsi" in result
    assert result["rsi"] is not None
    assert 0 <= result["rsi"] <= 100


def test_regime_tendencia():
    assert detectar_regimen(30.0) == "TENDENCIA"
    assert detectar_regimen(15.0) == "RANGO"
    assert detectar_regimen(22.0) == "TRANSICION"


def test_multi_timeframe_score():
    ind = {
        "4h": {"ema_medium": 110, "ema_slow": 100, "close": 115, "vwap": 105},
        "1h": {"ema_medium": 112, "ema_slow": 108, "close": 115, "vwap": 110},
        "15m": {"ema_medium": 114, "ema_slow": 113, "close": 115, "vwap": 114},
    }
    score = score_multi_timeframe(ind)
    assert score > 0


def test_sizing_basic():
    qty = calcular_tamano_posicion(10000, 100, 2.0, 0.8)
    assert qty > 0


def test_exits_long():
    levels = calcular_niveles_salida(100, 2.0, "LONG")
    assert levels["sl"] < 100
    assert levels["tp1"] > 100
    assert levels["tp2"] > levels["tp1"]
