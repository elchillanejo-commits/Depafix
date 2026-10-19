import pandas as pd
import pytest
from src.trading.trailing_stops import (
    atr_trail, bar_trail, debe_salir, ema_trail,
)


def _df() -> pd.DataFrame:
    return pd.DataFrame({
        "high": [10, 11, 12, 13, 14, 15, 16],
        "low":  [ 8,  9, 10, 11, 12, 13, 14],
        "close":[ 9, 10, 11, 12, 13, 14, 15],
    })


def test_bar_trail_long():
    # últimas 2 velas CERRADAS (índices 4 y 5): lows 12, 13 -> min 12
    assert bar_trail(_df(), "LONG", bars_back=2) == 12.0


def test_bar_trail_short():
    # últimas 2 velas CERRADAS (índices 4 y 5): highs 14, 15 -> max 15
    assert bar_trail(_df(), "SHORT", bars_back=2) == 15.0


def test_bar_trail_no_incluye_veta_actual():
    # Si incluyera la última vela (low=14), el min sería 14, no 12
    assert bar_trail(_df(), "LONG", bars_back=2) != 14.0


def test_atr_trail_long_menor_que_close():
    df = _df()
    stop = atr_trail(df, "LONG", atr_period=3, atr_factor=2.0)
    assert stop < float(df["close"].iloc[-1])


def test_atr_trail_short_mayor_que_close():
    df = _df()
    stop = atr_trail(df, "SHORT", atr_period=3, atr_factor=2.0)
    assert stop > float(df["close"].iloc[-1])


def test_ema_trail_long_y_short_iguales():
    df = _df()
    assert ema_trail(df, "LONG", 3) == ema_trail(df, "SHORT", 3)


def test_debe_salir_true_long():
    df = _df()
    # cierre actual = 15. stop = 20 (por encima) -> debe salir
    assert debe_salir(df, "LONG", stop_actual=20.0) is True


def test_debe_salir_false_long():
    df = _df()
    assert debe_salir(df, "LONG", stop_actual=10.0) is False


def test_debe_salir_true_short():
    df = _df()
    # cierre = 15. stop = 10 -> cierre > stop -> salir
    assert debe_salir(df, "SHORT", stop_actual=10.0) is True


def test_bar_trail_df_muy_corto():
    df = _df().iloc[:2]
    with pytest.raises(ValueError):
        bar_trail(df, "LONG", bars_back=2)


def test_direccion_invalida():
    with pytest.raises(ValueError):
        bar_trail(_df(), "ARRIBA")


def test_atr_factor_invalido():
    with pytest.raises(ValueError):
        atr_trail(_df(), "LONG", atr_factor=0)
