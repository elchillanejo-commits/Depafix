"""
04_bot_brain.py — Fases 4-7: Inteligencia del bot
"""

import logging, time
from datetime import datetime, timezone
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
import numpy as np
import config
from bot_core import BotCore, KrakenClient, SupabaseStore

logger = logging.getLogger("Brain")

class Indicators:
    @staticmethod
    def ema(prices, period):
        if len(prices) < period: return np.array([])
        mult = 2.0 / (period + 1)
        vals = np.zeros_like(prices)
        vals[period - 1] = np.mean(prices[:period])
        for i in range(period, len(prices)):
            vals[i] = (prices[i] - vals[i-1]) * mult + vals[i-1]
        return vals
    @staticmethod
    def rsi(prices, period=14):
        if len(prices) < period + 1: return np.array([])
        deltas = np.diff(prices)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        avg_g = np.zeros_like(prices); avg_l = np.zeros_like(prices)
        avg_g[period] = np.mean(gains[:period]); avg_l[period] = np.mean(losses[:period])
        for i in range(period+1, len(prices)):
            avg_g[i] = (avg_g[i-1]*(period-1) + gains[i-1])/period
            avg_l[i] = (avg_l[i-1]*(period-1) + losses[i-1])/period
        rs = avg_g / (avg_l + 1e-10)
        return 100 - (100 / (1 + rs))
    @staticmethod
    def macd(prices, fast=12, slow=26, signal=9):
        if len(prices) < slow: return np.array([]), np.array([]), np.array([])
        ema_f = Indicators.ema(prices, fast)
        ema_s = Indicators.ema(prices, slow)
        line = ema_f - ema_s
        sig = Indicators.ema(line, signal)
        return line, sig, line - sig
    @staticmethod
    def bollinger(prices, period=20, std_dev=2.0):
        if len(prices) < period: return np.array([]), np.array([]), np.array([])
        mid = np.concatenate([np.full(period-1, np.nan), np.convolve(prices, np.ones(period)/period, mode='valid')])
        std = np.array([np.std(prices[max(0,i-period+1):i+1]) for i in range(len(prices))])
        return mid + std_dev*std, mid, mid - std_dev*std
    @staticmethod
    def atr(high, low, close, period=14):
        if len(close) < 2: return np.array([])
        tr = np.maximum(np.maximum(high[1:]-low[1:], np.abs(high[1:]-close[:-1])), np.abs(low[1:]-close[:-1]))
        vals = np.zeros_like(close); vals[0] = np.nan; vals[1:period] = np.nan
        if len(tr) >= period:
            vals[period] = np.mean(tr[:period])
            for i in range(period+1, len(close)):
                vals[i] = (vals[i-1]*(period-1) + tr[i-1])/period
        return vals
    @staticmethod
    def volume_sma(volume, period=20):
        if len(volume) < period: return np.array([])
        return np.concatenate([np.full(period-1, np.nan), np.convolve(volume, np.ones(period)/period, mode='valid')])
    @staticmethod
    def calculate_all(candles):
        if len(candles) < 200: return None
        closes = np.array([c["close"] for c in candles])
        highs = np.array([c["high"] for c in candles])
        lows = np.array([c["low"] for c in candles])
        volumes = np.array([c["volume"] for c in candles])
        ind = config.INDICATORS
        ema9 = Indicators.ema(closes, ind["ema"]["fast"])
        ema21 = Indicators.ema(closes, ind["ema"]["medium"])
        ema50 = Indicators.ema(closes, ind["ema"]["slow"])
        ema200 = Indicators.ema(closes, ind["ema"]["long"])
        rsi14 = Indicators.rsi(closes, ind["rsi"]["period"])
        macd_l, macd_s, macd_h = Indicators.macd(closes, ind["macd"]["fast"], ind["macd"]["slow"], ind["macd"]["signal"])
        bb_u, bb_m, bb_l = Indicators.bollinger(closes, ind["bollinger"]["period"], ind["bollinger"]["std_dev"])
        atr14 = Indicators.atr(highs, lows, closes, ind["atr"]["period"])
        vol_sma = Indicators.volume_sma(volumes, ind["volume"]["sma_period"])
        vol_ratio = volumes / (vol_sma + 1e-10)
        last = len(candles) - 1
        def safe(arr): return round(float(arr[last]), 8) if not np.isnan(arr[last]) else None
        return {
            "pair": candles[0]["pair"], "timeframe": candles[0]["timeframe"], "timestamp": candles[last]["timestamp"],
            "ema_9": safe(ema9), "ema_21": safe(ema21), "ema_50": safe(ema50), "ema_200": safe(ema200),
            "rsi_14": safe(rsi14), "macd_line": safe(macd_l), "macd_signal": safe(macd_s), "macd_histogram": safe(macd_h),
            "bb_upper": safe(bb_u), "bb_middle": safe(bb_m), "bb_lower": safe(bb_l),
            "atr_14": safe(atr14), "volume_sma_20": safe(vol_sma), "volume_ratio": safe(vol_ratio),
        }

@dataclass
class SignalResult:
    signal_type: str
    score: int
    confidence: str
    reasons: List[str]
    price: float

class Strategy:
    def __init__(self):
        self.weights = config.STRATEGY["weights"]
        self.min_score = config.STRATEGY["min_score"]
    def _score_ema(self, ind, candles, direction):
        score, reasons = 0, []
        ema9, ema21, ema50, ema200 = ind.get("ema_9"), ind.get("ema_21"), ind.get("ema_50"), ind.get("ema_200")
        close = candles[-1]["close"]
        if direction == "BUY":
            if ema9 and ema21 and ema9 > ema21:
                score += self.weights["ema_trend"] * 0.7; reasons.append("EMA9 > EMA21 (alcista)")
            if ema50 and ema200 and ema50 > ema200:
                score += self.weights["ema_trend"] * 0.3; reasons.append("EMA50 > EMA200")
        else:
            if ema9 and ema21 and ema9 < ema21:
                score += self.weights["ema_trend"] * 0.7; reasons.append("EMA9 < EMA21 (bajista)")
            if ema50 and ema200 and ema50 < ema200:
                score += self.weights["ema_trend"] * 0.3; reasons.append("EMA50 < EMA200")
        return score, reasons
    def _score_rsi(self, ind, direction):
        score, reasons = 0, []
        rsi = ind.get("rsi_14")
        if rsi is None: return 0, []
        bl, bh = config.STRATEGY["rsi_buy_zone"]
        sl, sh = config.STRATEGY["rsi_sell_zone"]
        if direction == "BUY":
            if bl <= rsi <= bh: score = self.weights["rsi_momentum"]; reasons.append(f"RSI {rsi:.1f} en zona compra")
            elif rsi < bl: score = self.weights["rsi_momentum"] * 0.8; reasons.append(f"RSI {rsi:.1f} sobrevendido")
        else:
            if sl <= rsi <= sh: score = self.weights["rsi_momentum"]; reasons.append(f"RSI {rsi:.1f} en zona venta")
            elif rsi > sh: score = self.weights["rsi_momentum"] * 0.8; reasons.append(f"RSI {rsi:.1f} sobrecomprado")
        return score, reasons
    def _score_macd(self, ind):
        score, reasons = 0, []
        h, l, s = ind.get("macd_histogram"), ind.get("macd_line"), ind.get("macd_signal")
        if h is None or l is None or s is None: return 0, []
        if h > 0 and l > s: score = self.weights["macd_confirmation"]; reasons.append("MACD alcista")
        elif h < 0 and l < s: score = self.weights["macd_confirmation"]; reasons.append("MACD bajista")
        elif h > 0: score = self.weights["macd_confirmation"] * 0.5; reasons.append("MACD debil alcista")
        elif h < 0: score = self.weights["macd_confirmation"] * 0.5; reasons.append("MACD debil bajista")
        return score, reasons
    def _score_bb(self, ind, candles):
        score, reasons = 0, []
        close = candles[-1]["close"]
        u, l, m = ind.get("bb_upper"), ind.get("bb_lower"), ind.get("bb_middle")
        if not all([u, l, m]): return 0, []
        br = u - l
        if br == 0: return 0, []
        pos = (close - l) / br
        th = config.STRATEGY["bb_distance_threshold"]
        if pos < th: score = self.weights["bb_position"]; reasons.append(f"Precio cerca banda inferior ({pos:.2%})")
        elif pos > (1 - th): score = self.weights["bb_position"]; reasons.append(f"Precio cerca banda superior ({pos:.2%})")
        elif 0.4 <= pos <= 0.6: score = self.weights["bb_position"] * 0.3; reasons.append("Precio en media Bollinger")
        return score, reasons
    def _score_vol(self, ind):
        score, reasons = 0, []
        r = ind.get("volume_ratio")
        if r and r > 2.0: score = self.weights["volume_spike"]; reasons.append(f"Volumen {r:.1f}x promedio")
        elif r and r > 1.5: score = self.weights["volume_spike"] * 0.6; reasons.append(f"Volumen {r:.1f}x promedio")
        return score, reasons
    def evaluate(self, ind, candles, higher_tf_ind=None):
        close = candles[-1]["close"]
        buy_score, buy_reasons = 0, []
        for fn, args in [(self._score_ema, (ind, candles, "BUY")), (self._score_rsi, (ind, "BUY")),
                         (self._score_macd, (ind,)), (self._score_bb, (ind, candles)), (self._score_vol, (ind,))]:
            s, r = fn(*args); buy_score += s; buy_reasons.extend(r)
        if higher_tf_ind:
            ht9, ht21 = higher_tf_ind.get("ema_9"), higher_tf_ind.get("ema_21")
            if ht9 and ht21 and ht9 > ht21: buy_score += self.weights["multi_tf"]; buy_reasons.append("Multi-TF alcista")
        sell_score, sell_reasons = 0, []
        for fn, args in [(self._score_ema, (ind, candles, "SELL")), (self._score_rsi, (ind, "SELL")),
                         (self._score_macd, (ind,)), (self._score_bb, (ind, candles)), (self._score_vol, (ind,))]:
            s, r = fn(*args); sell_score += s; sell_reasons.extend(r)
        if higher_tf_ind:
            ht9, ht21 = higher_tf_ind.get("ema_9"), higher_tf_ind.get("ema_21")
            if ht9 and ht21 and ht9 < ht21: sell_score += self.weights["multi_tf"]; sell_reasons.append("Multi-TF bajista")
        buy_score, sell_score = round(buy_score), round(sell_score)
        if buy_score >= self.min_score and buy_score > sell_score:
            return SignalResult("BUY", min(buy_score, 100), "HIGH" if buy_score >= 80 else "MEDIUM" if buy_score >= 65 else "LOW", buy_reasons, close)
        elif sell_score >= self.min_score and sell_score > buy_score:
            return SignalResult("SELL", min(sell_score, 100), "HIGH" if sell_score >= 80 else "MEDIUM" if sell_score >= 65 else "LOW", sell_reasons, close)
        return SignalResult("HOLD", max(buy_score, sell_score), "LOW", [], close)

class RiskManager:
    def __init__(self, db):
        self.db = db; self.risk = config.RISK
    def check_drawdown(self):
        pnl = self.db.get_daily_pnl()
        dd = abs(pnl) / self.risk["capital_usd"] * 100 if self.risk["capital_usd"] > 0 else 0
        if dd >= self.risk["max_daily_drawdown_pct"]: return False, f"Drawdown {dd:.2f}% >= limite"
        return True, f"Drawdown OK: {dd:.2f}%"
    def check_exposure(self):
        open_t = self.db.get_open_trades()
        if len(open_t) >= self.risk["max_open_trades"]: return False, "Max trades abiertos"
        exp = sum(t["quantity"] * t["entry_price"] for t in open_t)
        max_exp = self.risk["capital_usd"] * (self.risk["max_exposure_pct"] / 100)
        if exp >= max_exp: return False, f"Exposicion {exp:.2f} >= limite {max_exp:.2f}"
        return True, f"Exposicion OK: {exp:.2f}/{max_exp:.2f}"
    def calc_size(self, entry, sl):
        risk_amt = self.risk["capital_usd"] * (self.risk["risk_per_trade_pct"] / 100)
        pr = abs(entry - sl)
        if pr == 0:
            return 0
        qty = risk_amt / pr
        # Limitar valor nominal al 10% del capital
        max_qty = (self.risk["capital_usd"] * 0.10) / entry
        qty = min(qty, max_qty)
        return round(qty, 8)
    def calc_stops(self, entry, atr, direction):
        sl_d = atr * self.risk["atr_sl_multiplier"]
        tp_d = atr * self.risk["atr_tp_multiplier"]
        if direction == "BUY": sl, tp = entry - sl_d, entry + tp_d
        else: sl, tp = entry + sl_d, entry - tp_d
        risk = abs(entry - sl)
        if risk > 0 and (abs(tp - entry) / risk) < self.risk["min_risk_reward_ratio"]:
            min_r = risk * self.risk["min_risk_reward_ratio"]
            tp = entry + min_r if direction == "BUY" else entry - min_r
        return round(sl, 8), round(tp, 8)

class Executor:
    def __init__(self, kraken, db, risk):
        self.kraken = kraken; self.db = db; self.risk = risk; self.paper = config.PAPER_TRADING
    def execute(self, signal, pair, ind, candles):
        ok, msg = self.risk.check_drawdown()
        if not ok: logger.warning(f"🚫 Bloqueado: {msg}"); return None
        ok, msg = self.risk.check_exposure()
        if not ok: logger.warning(f"🚫 Bloqueado: {msg}"); return None
        entry = signal.price
        atr = ind.get("atr_14", entry * 0.02)
        sl, tp = self.risk.calc_stops(entry, atr, signal.signal_type)
        qty = self.risk.calc_size(entry, sl)
        if qty <= 0: return None
        txid = None
        if self.paper:
            logger.info(f"📄 PAPER: {signal.signal_type} {pair} @ {entry} | Qty: {qty} | SL: {sl} | TP: {tp}")
        else:
            try:
                result = self.kraken.add_order(pair, "buy" if signal.signal_type == "BUY" else "sell", "market", qty)
                txid = result.get("txid", [None])[0]
                logger.info(f"✅ Orden: {txid}")
            except Exception as e:
                logger.error(f"❌ Error orden: {e}"); return None
        sid = self.db.insert_signals([{
            "pair": pair, "timeframe": candles[0]["timeframe"], "timestamp": candles[-1]["timestamp"],
            "signal_type": signal.signal_type, "score": signal.score, "confidence": signal.confidence,
            "reasons": signal.reasons, "price_at_signal": entry, "executed": True,
        }])
        if not sid: return None
        tid = self.db.insert_trade({
            "signal_id": sid, "pair": pair, "side": signal.signal_type, "entry_price": entry,
            "quantity": qty, "stop_loss": sl, "take_profit": tp, "status": "OPEN",
            "kraken_txid": txid, "paper_trade": self.paper,
        })
        return tid
    def check_open(self):
        for t in self.db.get_open_trades():
            try:
                price = float(self.kraken.get_ticker(t["pair"])["c"][0])
            except:
                continue
            side, sl, tp, entry, qty = t["side"], t["stop_loss"], t["take_profit"], t["entry_price"], t["quantity"]
            close, reason = False, ""
            if side == "BUY":
                if price <= sl: close, reason = True, "STOP_LOSS"
                elif price >= tp: close, reason = True, "TAKE_PROFIT"
            else:
                if price >= sl: close, reason = True, "STOP_LOSS"
                elif price <= tp: close, reason = True, "TAKE_PROFIT"
            if close:
                pnl = (price - entry) * qty if side == "BUY" else (entry - price) * qty
                pnl_pct = (pnl / (entry * qty)) * 100 if entry * qty > 0 else 0
                self.db.update_trade(t["id"], {"status": "CLOSED", "exit_price": price, "pnl": round(pnl, 4),
                    "pnl_percent": round(pnl_pct, 4), "closed_at": datetime.now(timezone.utc).isoformat()})
                logger.info(f"{'🟢' if pnl > 0 else '🔴'} Cerrado [{reason}] {t['pair']}: P&L ${pnl:.2f}")

class Brain:
    def __init__(self, core):
        self.core = core; self.kraken = core.kraken; self.db = core.db
        self.strategy = Strategy(); self.risk = RiskManager(self.db)
        self.executor = Executor(self.kraken, self.db, self.risk)
    def analyze(self, pair, tf):
        candles = self.db.get_latest_ohlcv(pair, tf, 250)
        if len(candles) < 200:
            logger.warning(f"⚠️ Datos insuficientes {pair} ({len(candles)} velas)"); return None
        ind = Indicators.calculate_all(candles)
        if not ind: return None
        self.db.insert_indicators([ind])
        ht_ind = None
        ht_map = {60: 240, 240: 1440}
        if tf in ht_map:
            ht = self.db.get_latest_ohlcv(pair, ht_map[tf], 250)
            if len(ht) >= 200: ht_ind = Indicators.calculate_all(ht)
        sig = self.strategy.evaluate(ind, candles, ht_ind)
        if sig.signal_type != "HOLD":
            logger.info(f"📡 {sig.signal_type} {pair} {config.TF_MAP.get(tf, tf)} | Score: {sig.score}/100 | {sig.confidence}")
            for r in sig.reasons: logger.info(f"   → {r}")
        return sig
    def run_cycle(self, pairs_tfs):
        logger.info("=" * 60); logger.info("🧠 CICLO DE TRADING"); logger.info("=" * 60)
        for pair, tf in pairs_tfs:
            try: self.core.fetch_and_store(pair, tf); time.sleep(0.5)
            except Exception as e: logger.error(f"Error fetch {pair}: {e}")
        signals = 0
        for pair, tf in pairs_tfs:
            try:
                sig = self.analyze(pair, tf)
                if sig and sig.signal_type != "HOLD":
                    signals += 1
                    if sig.score >= config.STRATEGY["min_score"]:
                        ind = Indicators.calculate_all(self.db.get_latest_ohlcv(pair, tf, 250))
                        self.executor.execute(sig, pair, ind, self.db.get_latest_ohlcv(pair, tf, 250))
            except Exception as e: logger.error(f"Error analisis {pair}: {e}")
        self.executor.check_open()
        logger.info(f"🏁 Ciclo | Senales: {signals} | Abiertos: {len(self.db.get_open_trades())}")
        return signals

if __name__ == "__main__":
    core = BotCore(); brain = Brain(core); brain.run_cycle(config.PARES_TIMEFRAMES)
