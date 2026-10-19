"""Trailing stops para trend/momentum (metodología SMB Capital).

Tres tipos:
  - bar_trail:  extremo de las últimas N velas CERRADAS (no incluye actual).
  - atr_trail:  close ± (ATR * factor).
  - ema_trail:  EMA del precio.

Convención: LONG busca mínimos, SHORT busca máximos.
"""
from __future__ import annotations

import pandas as pd

PERIODOS_ATR_DEFAULT = 3
FACTOR_ATR_DEFAULT = 3.0
EMA_PERIOD_DEFAULT = 9

_DIRECCIONES = ("LONG", "SHORT")


def _validar_direccion(direccion: str) -> None:
    if direccion not in _DIRECCIONES:
        raise ValueError(f"direccion debe ser {_DIRECCIONES}, recibido '{direccion}'")


def bar_trail(df: pd.DataFrame, direccion: str, bars_back: int = 2) -> float:
    """Extremo de las últimas `bars_back` velas CERRADAS.

    Excluye la vela actual (que puede estar en formación).
    LONG  -> min(low) de las N velas cerradas previas.
    SHORT -> max(high) de las N velas cerradas previas.
    """
    _validar_direccion(direccion)
    if bars_back < 1:
        raise ValueError(f"bars_back debe ser >=1, recibido {bars_back}")
    if len(df) < bars_back + 1:
        raise ValueError(
            f"df necesita >= {bars_back + 1} velas, tiene {len(df)}"
        )
    ventana = df.iloc[-(bars_back + 1):-1]
    if direccion == "LONG":
        return float(ventana["low"].min())
    return float(ventana["high"].max())


def _atr(df: pd.DataFrame, periodo: int) -> float:
    """ATR simple (media de True Range de las últimas `periodo` velas)."""
    if len(df) < periodo + 1:
        raise ValueError(
            f"df necesita >= {periodo + 1} velas para ATR, tiene {len(df)}"
        )
    h = df["high"]
    l = df["low"]
    c_prev = df["close"].shift(1)
    tr = pd.concat([
        h - l,
        (h - c_prev).abs(),
        (l - c_prev).abs(),
    ], axis=1).max(axis=1)
    return float(tr.iloc[-periodo:].mean())


def atr_trail(
    df: pd.DataFrame,
    direccion: str,
    atr_period: int = PERIODOS_ATR_DEFAULT,
    atr_factor: float = FACTOR_ATR_DEFAULT,
) -> float:
    """Stop dinámico basado en ATR. LONG resta, SHORT suma."""
    _validar_direccion(direccion)
    if atr_factor <= 0:
        raise ValueError(f"atr_factor debe ser >0, recibido {atr_factor}")
    atr = _atr(df, atr_period)
    cierre = float(df["close"].iloc[-1])
    if direccion == "LONG":
        return cierre - atr * atr_factor
    return cierre + atr * atr_factor


def ema_trail(
    df: pd.DataFrame,
    direccion: str,
    ema_period: int = EMA_PERIOD_DEFAULT,
) -> float:
    """Stop en la EMA. Mismo valor para LONG y SHORT (la dirección
    determina si el precio está por encima o debajo)."""
    _validar_direccion(direccion)
    if len(df) < ema_period:
        raise ValueError(
            f"df necesita >= {ema_period} velas para EMA, tiene {len(df)}"
        )
    ema = df["close"].ewm(span=ema_period, adjust=False).mean()
    return float(ema.iloc[-1])


def debe_salir(df: pd.DataFrame, direccion: str, stop_actual: float) -> bool:
    """True si el cierre actual rompió el stop."""
    _validar_direccion(direccion)
    cierre = float(df["close"].iloc[-1])
    if direccion == "LONG":
        return cierre < stop_actual
    return cierre > stop_actual
