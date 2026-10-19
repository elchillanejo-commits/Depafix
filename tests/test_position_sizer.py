import pytest
from src.trading.position_sizer import get_position_size, kelly_optimo


def test_kelly_optimo_normal():
    # win 60%, ratio 1.5 -> kelly = (0.6-0.4)/1.5 = 0.133
    k = kelly_optimo(0.6, 1.5)
    assert 0.13 < k < 0.14


def test_kelly_optimo_negativo():
    # win 30%, ratio 1 -> kelly = (0.3-0.7)/1 = -0.4 -> clamp 0
    assert kelly_optimo(0.3, 1.0) == 0.0


def test_kelly_optimo_clamp_max():
    # win 90%, ratio 1 -> kelly = 0.8 -> clamp 0.25
    assert kelly_optimo(0.9, 1.0) == 0.25


def test_kelly_optimo_win_rate_invalido():
    with pytest.raises(ValueError):
        kelly_optimo(1.5, 1.0)
    with pytest.raises(ValueError):
        kelly_optimo(-0.1, 1.0)


def test_kelly_optimo_ratio_invalido():
    with pytest.raises(ValueError):
        kelly_optimo(0.6, 0.0)


def test_position_size_trend_up():
    p = get_position_size(1000.0, "TREND_UP", 0.6, 1.5)
    assert p > 0
    assert p <= 1000.0 * 0.05  # hard cap


def test_position_size_trend_down():
    p = get_position_size(1000.0, "TREND_DOWN", 0.6, 1.5)
    assert p > 0


def test_position_size_range():
    assert get_position_size(1000.0, "RANGE", 0.6, 1.5) == 0.0


def test_position_size_volatile():
    p = get_position_size(1000.0, "VOLATILE", 0.6, 1.5)
    assert p > 0
    assert p < 1000.0


def test_position_size_regimen_desconocido():
    assert get_position_size(1000.0, "RANDOM", 0.6, 1.5) == 0.0


def test_position_size_kelly_negativo():
    assert get_position_size(1000.0, "TREND_UP", 0.1, 1.0) == 0.0


def test_position_size_capital_cero():
    assert get_position_size(0.0, "TREND_UP", 0.6, 1.5) == 0.0


def test_position_size_capital_negativo():
    assert get_position_size(-100.0, "TREND_UP", 0.6, 1.5) == 0.0
