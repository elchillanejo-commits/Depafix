from __future__ import annotations

import numpy as np
import pandas as pd

from src.trading.walkforward import (
    dividir_ventanas, evaluar_estrategia, sharpe_ratio, walkforward,
)


def _df_ohlc(n: int = 300, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    precios = 100.0 + np.cumsum(rng.normal(0, 1, n))
    return pd.DataFrame({
        "open": precios,
        "high": precios + 1.0,
        "low": precios - 1.0,
        "close": precios + rng.normal(0, 0.5, n),
        "volume": rng.integers(1000, 10000, n),
    })


def test_sharpe_ratio_normal() -> None:
    rng = np.random.default_rng(0)
    r = pd.Series(rng.normal(0.001, 0.01, 500))
    s = sharpe_ratio(r, periodos_anuales=365)
    assert isinstance(s, float) and np.isfinite(s) and s != 0.0


def test_sharpe_ratio_std_cero() -> None:
    assert sharpe_ratio(pd.Series([0.01] * 100)) == 0.0
    assert sharpe_ratio(pd.Series([], dtype=float)) == 0.0
    assert sharpe_ratio(pd.Series([0.01])) == 0.0


def test_dividir_ventanas_grande() -> None:
    ventanas = dividir_ventanas(_df_ohlc(300), n_ventanas=3, pct_entrenamiento=0.7)
    assert len(ventanas) == 3
    for train, test in ventanas:
        assert len(train) > 0 and len(test) > 0
        ratio = len(train) / (len(train) + len(test))
        assert 0.6 <= ratio <= 0.8


def test_dividir_ventanas_chico() -> None:
    assert dividir_ventanas(_df_ohlc(3), n_ventanas=3) == []


def test_walkforward_estrategia_constante() -> None:
    df = _df_ohlc(300)
    def estrategia(d: pd.DataFrame) -> pd.Series:
        return pd.Series(0.01, index=d.index)
    res = walkforward(df, estrategia, n_ventanas=3)
    assert len(res["ventanas"]) == 3
    assert res["degradacion_promedio_pct"] == 0.0
    assert res["es_robusta"] is True


def test_walkforward_estructura_aleatoria() -> None:
    df = _df_ohlc(300)
    rng = np.random.default_rng(7)
    def estrategia(d: pd.DataFrame) -> pd.Series:
        return pd.Series(rng.normal(0, 0.01, len(d)), index=d.index)
    res = walkforward(df, estrategia, n_ventanas=3)
    assert set(res.keys()) == {
        "ventanas", "sharpe_promedio_train", "sharpe_promedio_test",
        "degradacion_promedio_pct", "es_robusta",
    }
    assert len(res["ventanas"]) == 3
    for v in res["ventanas"]:
        assert set(v.keys()) == {"i", "sharpe_train", "sharpe_test", "degradacion_pct"}
    assert isinstance(res["es_robusta"], bool)
