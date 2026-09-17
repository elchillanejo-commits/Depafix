"""Confirmación multi-timeframe con pesos ponderados."""
from typing import Dict
from config import TF_WEIGHTS


def evaluar_tendencia_tf(ind: Dict) -> int:
    """Retorna 1 (alcista), -1 (bajista), 0 (lateral)."""
    ema_med = ind.get("ema_medium")
    ema_slow = ind.get("ema_slow")
    close = ind.get("close")
    vwap = ind.get("vwap")

    if None in (ema_med, ema_slow, close, vwap):
        return 0

    if ema_med > ema_slow and close > vwap:
        return 1
    if ema_med < ema_slow and close < vwap:
        return -1
    return 0


def score_multi_timeframe(indicators_by_tf: Dict[str, Dict]) -> float:
    """
    Calcula score de confianza ponderado por timeframe.
    indicators_by_tf: {"4h": {...}, "1h": {...}, "15m": {...}}
    Retorna score entre -1.0 y 1.0.
    """
    score = 0.0
    total_weight = 0.0

    for tf, weight in TF_WEIGHTS.items():
        ind = indicators_by_tf.get(tf, {})
        trend = evaluar_tendencia_tf(ind)
        score += trend * weight
        total_weight += weight

    if total_weight == 0:
        return 0.0
    return score / total_weight


def gatillo_15m(ind_15m: Dict, direction: str) -> bool:
    """Evalúa si el timeframe 15m dispara entrada."""
    ema_fast = ind_15m.get("ema_fast")
    ema_med = ind_15m.get("ema_medium")
    stoch_k = ind_15m.get("stoch_rsi_k")

    if None in (ema_fast, ema_med, stoch_k):
        return False

    if direction == "LONG":
        return ema_fast > ema_med and stoch_k < 0.20
    elif direction == "SHORT":
        return ema_fast < ema_med and stoch_k > 0.80
    return False
