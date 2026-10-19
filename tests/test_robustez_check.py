from __future__ import annotations

import asyncio

import numpy as np
import pandas as pd

from src.trading.robustez_check import (
    MIN_VELAS,
    _retornos_desde_senales,
    evaluar_par,
    validar_robustez,
)


def _df_sintetico(n: int, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    precios = 100.0 + np.cumsum(rng.normal(0, 1, n))
    return pd.DataFrame({
        "tiempo": pd.date_range("2026-01-01", periods=n, freq="h"),
        "open": precios,
        "high": precios + 1.0,
        "low": precios - 1.0,
        "close": precios + rng.normal(0, 0.5, n),
        "volume": rng.integers(1000, 10000, n),
    })


def test_evaluar_par_pocos_datos():
    df = _df_sintetico(100)
    r = evaluar_par(df)
    assert r["estado"] == "pocos_datos"
    assert r["velas"] == 100
    assert r["min_requerido"] == MIN_VELAS


def test_evaluar_par_suficientes_velas():
    df = _df_sintetico(MIN_VELAS + 50)
    r = evaluar_par(df, n_ventanas=2)
    assert r["estado"] in ("ok", "error")


def test_retornos_compra_con_precio_subiendo():
    df = pd.DataFrame({"close": [100.0, 101.0, 102.0, 103.0]})
    senales = pd.Series(["COMPRA", "COMPRA", "COMPRA", "COMPRA"], index=df.index)
    rets = _retornos_desde_senales(df, senales)
    assert rets.iloc[0] == 0.0
    assert rets.iloc[1] > 0


def test_retornos_venta_con_precio_subiendo():
    df = pd.DataFrame({"close": [100.0, 101.0, 102.0, 103.0]})
    senales = pd.Series(["VENTA", "VENTA", "VENTA", "VENTA"], index=df.index)
    rets = _retornos_desde_senales(df, senales)
    assert rets.iloc[1] < 0


def test_retornos_espera_es_cero():
    df = pd.DataFrame({"close": [100.0, 101.0, 102.0, 103.0]})
    senales = pd.Series(["ESPERA"] * 4, index=df.index)
    rets = _retornos_desde_senales(df, senales)
    assert all(r == 0.0 for r in rets)


def test_validar_robustez_pocos_datos():
    """Sin pytest-asyncio, usar asyncio.run() directo."""
    class FakeClient:
        def table(self, _): return self
        def select(self, _): return self
        def eq(self, *a): return self
        def order(self, *a, **k): return self
        def limit(self, _): return self
        def execute(self):
            return type("R", (), {"data": [{"tiempo": "2026-01-01", "cierre": 100}]})()

    r = asyncio.run(validar_robustez(FakeClient(), ["BTC/USD"]))
    assert r["robusta"] is None
    assert r["motivo"] == "sin_datos_suficientes"
