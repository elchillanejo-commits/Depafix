"""Indicadores técnicos incrementales + nuevos (VWAP, ATR, StochRSI, OBV, ADX)."""
import numpy as np
import pandas as pd
from typing import Dict, List, Optional

from config import (
    RSI_WINDOW, STOCH_RSI_WINDOW, ATR_WINDOW,
    BB_WINDOW, BB_STD, ADX_WINDOW,
    EMA_FAST, EMA_MEDIUM, EMA_SLOW,
)


class IndicadoresTecnicos:
    """Calcula indicadores manteniendo estado interno por (pair, timeframe)."""
    def __init__(self, max_len: int = 5000):
        self.max_len = max_len
        self._history: Dict[tuple, pd.DataFrame] = {}

    def update(self, pair: str, timeframe: str, new_candles: List[Dict]) -> Dict:
        key = (pair, timeframe)
        df = self._history.get(key)
        new_df = pd.DataFrame(new_candles)
        if new_df.empty:
            return self._last_values(key) if df is not None else {}

        if df is None:
            df = new_df
        else:
            df = pd.concat([df, new_df], ignore_index=True)

        if len(df) > self.max_len:
            df = df.iloc[-self.max_len:].reset_index(drop=True)

        self._history[key] = df
        return self._compute(df)

    def _last_values(self, key: tuple) -> Dict:
        df = self._history.get(key)
        if df is None or len(df) < 30:
            return {}
        return self._compute(df, last_only=True)

    def _compute(self, df: pd.DataFrame, last_only: bool = False) -> Dict:
        close = df["close"].values
        high = df["high"].values
        low = df["low"].values
        volume = df["volume"].values

        # EMAs
        ema_fast = self._ema(close, EMA_FAST)
        ema_med = self._ema(close, EMA_MEDIUM)
        ema_slow = self._ema(close, EMA_SLOW)

        # RSI
        rsi = self._rsi(close, RSI_WINDOW)

        # ATR
        atr = self._atr(high, low, close, ATR_WINDOW)

        # Stochastic RSI
        stoch_k, stoch_d = self._stoch_rsi(close, STOCH_RSI_WINDOW)

        # VWAP (acumulado desde el inicio del DataFrame)
        vwap = self._vwap(high, low, close, volume)

        # OBV
        obv = self._obv(close, volume)

        # Bollinger
        bb_mid, bb_up, bb_low = self._bollinger(close, BB_WINDOW, BB_STD)

        # ADX
        adx = self._adx(high, low, close, ADX_WINDOW)

        def last(arr):
            return float(arr[-1]) if len(arr) > 0 else None

        if last_only:
            return {
                "ema_fast": last(ema_fast), "ema_medium": last(ema_med), "ema_slow": last(ema_slow),
                "rsi": last(rsi), "atr": last(atr),
                "stoch_rsi_k": last(stoch_k), "stoch_rsi_d": last(stoch_d),
                "vwap": last(vwap), "obv": last(obv),
                "bb_upper": last(bb_up), "bb_lower": last(bb_low), "bb_middle": last(bb_mid),
                "adx": last(adx),
            }

        return {
            "ema_fast": last(ema_fast), "ema_medium": last(ema_med), "ema_slow": last(ema_slow),
            "rsi": last(rsi), "atr": last(atr),
            "stoch_rsi_k": last(stoch_k), "stoch_rsi_d": last(stoch_d),
            "vwap": last(vwap), "obv": last(obv),
            "bb_upper": last(bb_up), "bb_lower": last(bb_low), "bb_middle": last(bb_mid),
            "adx": last(adx),
        }

    @staticmethod
    def _ema(arr: np.ndarray, span: int) -> np.ndarray:
        return pd.Series(arr).ewm(span=span, adjust=False).mean().values

    @staticmethod
    def _rsi(arr: np.ndarray, window: int) -> np.ndarray:
        s = pd.Series(arr)
        delta = s.diff()
        gain = delta.clip(lower=0)
        loss = (-delta).clip(lower=0)
        avg_gain = gain.ewm(alpha=1 / window, min_periods=window).mean()
        avg_loss = loss.ewm(alpha=1 / window, min_periods=window).mean()
        rs = avg_gain / (avg_loss + 1e-9)
        rsi = 100 - (100 / (1 + rs))
        return rsi.values

    @staticmethod
    def _atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, window: int) -> np.ndarray:
        h = pd.Series(high)
        l = pd.Series(low)
        c = pd.Series(close)
        tr1 = h - l
        tr2 = (h - c.shift()).abs()
        tr3 = (l - c.shift()).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.ewm(alpha=1 / window, min_periods=window).mean()
        return atr.values

    @staticmethod
    def _stoch_rsi(arr: np.ndarray, window: int) -> tuple:
        s = pd.Series(arr)
        rsi = IndicadoresTecnicos._rsi(arr, window)
        rsi_s = pd.Series(rsi)
        min_rsi = rsi_s.rolling(window=window, min_periods=window).min()
        max_rsi = rsi_s.rolling(window=window, min_periods=window).max()
        stoch = (rsi_s - min_rsi) / (max_rsi - min_rsi + 1e-9)
        k = stoch.rolling(window=3, min_periods=3).mean()
        d = k.rolling(window=3, min_periods=3).mean()
        return k.values, d.values

    @staticmethod
    def _vwap(high: np.ndarray, low: np.ndarray, close: np.ndarray, volume: np.ndarray) -> np.ndarray:
        typical = (pd.Series(high) + pd.Series(low) + pd.Series(close)) / 3
        cum_vol = pd.Series(volume).cumsum()
        cum_tp_vol = (typical * pd.Series(volume)).cumsum()
        return (cum_tp_vol / (cum_vol + 1e-9)).values

    @staticmethod
    def _obv(close: np.ndarray, volume: np.ndarray) -> np.ndarray:
        c = pd.Series(close)
        v = pd.Series(volume)
        obv = (np.sign(c.diff()) * v).fillna(0).cumsum()
        return obv.values

    @staticmethod
    def _bollinger(arr: np.ndarray, window: int, num_std: float) -> tuple:
        s = pd.Series(arr)
        mid = s.rolling(window=window, min_periods=window).mean()
        std = s.rolling(window=window, min_periods=window).std(ddof=0)
        return mid.values, (mid + num_std * std).values, (mid - num_std * std).values

    @staticmethod
    def _adx(high: np.ndarray, low: np.ndarray, close: np.ndarray, window: int) -> np.ndarray:
        h = pd.Series(high)
        l = pd.Series(low)
        c = pd.Series(close)

        tr1 = h - l
        tr2 = (h - c.shift()).abs()
        tr3 = (l - c.shift()).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        plus_dm = (h - h.shift()).clip(lower=0)
        minus_dm = (l.shift() - l).clip(lower=0)
        plus_dm[plus_dm < minus_dm] = 0
        minus_dm[minus_dm < plus_dm] = 0

        atr = tr.ewm(alpha=1 / window, min_periods=window).mean()
        plus_di = 100 * plus_dm.ewm(alpha=1 / window, min_periods=window).mean() / (atr + 1e-9)
        minus_di = 100 * minus_dm.ewm(alpha=1 / window, min_periods=window).mean() / (atr + 1e-9)
        dx = (abs(plus_di - minus_di) / (plus_di + minus_di + 1e-9)) * 100
        adx = dx.ewm(alpha=1 / window, min_periods=window).mean()
        return adx.values
