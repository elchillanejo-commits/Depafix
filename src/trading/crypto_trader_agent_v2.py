"""crypto_trader_agent.py — DepaFix Trading Agent v2"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Literal
import numpy as np
import pandas as pd

EMA_RAPIDA = 20
EMA_LENTA = 50
RSI_PERIOD = 14
FIB_LOOKBACK = 40
GOLDEN_POCKET_MIN = 0.618
GOLDEN_POCKET_MAX = 0.786
FVG_LOOKBACK = 20
OB_LOOKBACK = 30
SCORE_MINIMO = 3
RATIO_RIESGO_BENEFICIO = 1.5
UMBRAL_TENDENCIA = 0.002

Senal = Literal["COMPRA", "VENTA", "ESPERA"]


def ema(serie, periodo):
    return serie.ewm(span=periodo, adjust=False).mean()


def rsi(serie, periodo=RSI_PERIOD):
    delta = serie.diff()
    g = delta.clip(lower=0.0)
    p = -delta.clip(upper=0.0)
    mg = g.ewm(alpha=1 / periodo, adjust=False).mean()
    mp = p.ewm(alpha=1 / periodo, adjust=False).mean()
    rs = mg / mp.replace(0.0, np.nan)
    return (100 - 100 / (1 + rs)).fillna(50.0)


def factor_tendencia(df):
    if len(df) < EMA_LENTA + EMA_RAPIDA:
        return False, False
    e50 = ema(df["close"], EMA_LENTA)
    actual = float(e50.iloc[-1])
    previo = float(e50.iloc[-1 - EMA_RAPIDA])
    u = UMBRAL_TENDENCIA * abs(actual)
    return actual - previo > u, previo - actual > u


def factor_rsi(df):
    if len(df) < RSI_PERIOD + 5:
        return False, False
    s = rsi(df["close"], RSI_PERIOD)
    a = float(s.iloc[-1])
    p = float(s.iloc[-4])
    return (a <= 45 and a > p) or (p < 50 <= a), (a >= 55 and a < p) or (p > 50 >= a)


def factor_golden_pocket(df):
    if len(df) < FIB_LOOKBACK + 2:
        return False, False, float(df["low"].min()), float(df["high"].max())
    v = df.iloc[-FIB_LOOKBACK:]
    sh = float(v["high"].max())
    sl = float(v["low"].min())
    r = sh - sl
    if r <= 0:
        return False, False, sl, sh
    ih = int(v["high"].to_numpy().argmax())
    il = int(v["low"].to_numpy().argmin())
    p = float(df["close"].iloc[-1])
    gal = sh - r * GOLDEN_POCKET_MAX
    gah = sh - r * GOLDEN_POCKET_MIN
    alc = il < ih and gal <= p <= gah
    gbl = sl + r * GOLDEN_POCKET_MIN
    gbh = sl + r * GOLDEN_POCKET_MAX
    baj = ih < il and gbl <= p <= gbh
    return alc, baj, sl, sh


def factor_fvg(df):
    if len(df) < FVG_LOOKBACK + 2:
        return False, False
    v = df.iloc[-FVG_LOOKBACK:]
    h = v["high"].to_numpy()
    l = v["low"].to_numpy()
    p = float(df["close"].iloc[-1])
    fa = False
    fb = False
    for i in range(1, len(v) - 1):
        if l[i + 1] > h[i - 1] and p > h[i - 1]:
            fa = True
        if h[i + 1] < l[i - 1] and p < l[i - 1]:
            fb = True
    return fa, fb


def factor_order_block(df):
    if len(df) < OB_LOOKBACK + 3:
        return False, False
    v = df.iloc[-OB_LOOKBACK:].reset_index(drop=True)
    o = v["open"].to_numpy()
    c = v["close"].to_numpy()
    h = v["high"].to_numpy()
    l = v["low"].to_numpy()
    tr = np.maximum(h[1:] - l[1:], np.maximum(np.abs(h[1:] - c[:-1]), np.abs(l[1:] - c[:-1])))
    atr = float(tr.mean()) if len(tr) else 0.0
    if atr == 0:
        return False, False
    p = float(df["close"].iloc[-1])
    oa = False
    ob = False
    for i in range(1, len(v) - 3):
        if c[i + 2] - c[i] > 1.5 * atr and c[i] < o[i] and p >= l[i]:
            oa = True
        if c[i] - c[i + 2] > 1.5 * atr and c[i] > o[i] and p <= h[i]:
            ob = True
    return oa, ob
    
    




@dataclass
class Resultado:
    senal: Senal
    score_alcista: int
    score_bajista: int
    confluencia_detalle: list = field(default_factory=list)
    precio_entrada: float = 0.0
    stop_loss: float = None
    take_profit_1: float = None
    swing_low: float = 0.0
    swing_high: float = 0.0


def analizar(df):
    minimo = max(EMA_LENTA, RSI_PERIOD, FIB_LOOKBACK, FVG_LOOKBACK, OB_LOOKBACK) + 5
    if len(df) < minimo:
        raise ValueError(f"Se necesitan >= {minimo} velas, hay {len(df)}")
    df = df.copy()
    p = float(df["close"].iloc[-1])
    fa = []
    fb = []

    ta, tb = factor_tendencia(df)
    if ta: fa.append("EMA50 alcista")
    if tb: fb.append("EMA50 bajista")

    ra, rb = factor_rsi(df)
    rv = float(rsi(df["close"], RSI_PERIOD).iloc[-1])
    if ra: fa.append(f"RSI={rv:.1f} rebote")
    if rb: fb.append(f"RSI={rv:.1f} giro")

    ga, gb, sl, sh = factor_golden_pocket(df)
    if ga: fa.append("Golden Pocket retroceso")
    if gb: fb.append("Golden Pocket rebote")

    va, vb = factor_fvg(df)
    if va: fa.append("FVG alcista")
    if vb: fb.append("FVG bajista")

    oa, ob = factor_order_block(df)
    if oa: fa.append("OB alcista")
    if ob: fb.append("OB bajista")

    sa = len(fa)
    sb = len(fb)

    if sa >= SCORE_MINIMO and sa > sb:
        senal = "COMPRA"
        detalle = fa
        stop_loss = sl
        r = max(p - stop_loss, 1e-9)
        tp = p + r * RATIO_RIESGO_BENEFICIO
    elif sb >= SCORE_MINIMO and sb > sa:
        senal = "VENTA"
        detalle = fb
        stop_loss = sh
        r = max(stop_loss - p, 1e-9)
        tp = p - r * RATIO_RIESGO_BENEFICIO
    else:
        senal = "ESPERA"
        detalle = fa + fb
        stop_loss = None
        tp = None

    return Resultado(
        senal=senal, score_alcista=sa, score_bajista=sb,
        confluencia_detalle=detalle, precio_entrada=p,
        stop_loss=stop_loss, take_profit_1=tp,
        swing_low=sl, swing_high=sh,
    )


def _velas(cierres, spread=1.0):
    cierres = [float(x) for x in cierres]
    opens = [cierres[0]] + cierres[:-1]
    highs = [max(o, c) + spread * 0.5 for o, c in zip(opens, cierres)]
    lows = [min(o, c) - spread * 0.5 for o, c in zip(opens, cierres)]
    return pd.DataFrame({"open": opens, "high": highs, "low": lows,
                         "close": cierres, "volume": [1.0] * len(cierres)})


def _datos_alcista():
    c = []
    p = 100.0
    for _ in range(180): p += 0.5; c.append(p)
    for _ in range(20): p += 1.0; c.append(p)
    for _ in range(15): p -= 0.8; c.append(p)
    for _ in range(20): p += 0.7; c.append(p)
    return _velas(c)


def _datos_bajista():
    c = []
    p = 300.0
    for _ in range(180): p -= 0.5; c.append(p)
    for _ in range(20): p -= 1.0; c.append(p)
    for _ in range(15): p += 0.8; c.append(p)
    for _ in range(20): p -= 0.7; c.append(p)
    return _velas(c)


def _datos_lateral():
    return _velas([100.0] * 230)


def _show(t, r):
    print(f"\n[{t}]")
    print(f"  senal = {r.senal}")
    print(f"  alcista={r.score_alcista} bajista={r.score_bajista}")
    print(f"  sl={r.stop_loss} tp={r.take_profit_1}")
    print(f"  detalle={r.confluencia_detalle}")


if __name__ == "__main__":
    _show("ALCISTA", analizar(_datos_alcista()))
    _show("BAJISTA", analizar(_datos_bajista()))
    _show("LATERAL", analizar(_datos_lateral()))
    print("\nOK")
