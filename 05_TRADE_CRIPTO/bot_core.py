"""
03_bot_core.py — Fases 1-3: Infraestructura + Kraken + Calidad de datos
"""

import time, hashlib, hmac, base64, json, logging
from datetime import datetime, timezone
from typing import List, Dict, Optional, Tuple
from urllib.parse import urlencode
import requests
from supabase import create_client, Client
import config

logging.basicConfig(level=getattr(logging, config.LOG_LEVEL), format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")
logger = logging.getLogger("BotCore")

class KrakenClient:
    BASE_URL = "https://api.kraken.com"
    def __init__(self, api_key, api_secret):
        self.api_key, self.api_secret = api_key, api_secret
        self.session = requests.Session()
    def _sign(self, urlpath, data):
        postdata = urlencode(data)
        encoded = (str(data["nonce"]) + postdata).encode()
        message = urlpath.encode() + hashlib.sha256(encoded).digest()
        return base64.b64encode(hmac.new(base64.b64decode(self.api_secret), message, hashlib.sha512).digest()).decode()
    def _request(self, method, endpoint, payload=None, private=False):
        url = f"{self.BASE_URL}{endpoint}"
        headers = {}
        if private:
            payload = payload or {}
            payload["nonce"] = int(time.time() * 1000)
            headers = {"API-Key": self.api_key, "API-Sign": self._sign(endpoint, payload)}
        for attempt in range(config.EXECUTION["max_retries"]):
            try:
                if method.upper() == "GET":
                    resp = self.session.get(url, params=payload, headers=headers, timeout=config.EXECUTION["kraken_timeout"])
                else:
                    resp = self.session.post(url, data=payload, headers=headers, timeout=config.EXECUTION["kraken_timeout"])
                resp.raise_for_status()
                data = resp.json()
                if data.get("error"):
                    raise RuntimeError(f"Kraken API error: {data['error']}")
                return data["result"]
            except Exception as e:
                logger.warning(f"Request fallo (intento {attempt+1}/{config.EXECUTION['max_retries']}): {e}")
                if attempt < config.EXECUTION["max_retries"] - 1:
                    time.sleep(config.EXECUTION["retry_delay"] * (attempt + 1))
                else:
                    raise
    def get_ohlc(self, pair, interval=60, since=None):
        kraken_pair = pair.replace("/", "")
        payload = {"pair": kraken_pair, "interval": interval}
        if since: payload["since"] = since
        result = self._request("GET", "/0/public/OHLC", payload)
        return result[list(result.keys())[0]]
    def get_ticker(self, pair):
        kraken_pair = pair.replace("/", "")
        result = self._request("GET", "/0/public/Ticker", {"pair": kraken_pair})
        return result[list(result.keys())[0]]
    def get_balance(self):
        return self._request("POST", "/0/private/Balance", private=True)
    def add_order(self, pair, side, ordertype, volume, price=None, leverage=None):
        payload = {"pair": pair.replace("/", ""), "type": side.lower(), "ordertype": ordertype, "volume": str(volume)}
        if price: payload["price"] = str(price)
        if leverage: payload["leverage"] = leverage
        return self._request("POST", "/0/private/AddOrder", payload, private=True)

class SupabaseStore:
    def __init__(self, url, key):
        self.client = create_client(url, key)
        logger.info("Conectado a Supabase")
    def insert_ohlcv_batch(self, records):
        if not records: return 0
        inserted = 0
        batch_size = config.EXECUTION["batch_size"]
        for i in range(0, len(records), batch_size):
            batch = records[i:i + batch_size]
            try:
                self.client.table("ohlcv").upsert(batch, on_conflict="pair,timeframe,timestamp").execute()
                inserted += len(batch)
            except Exception as e:
                logger.error(f"Error insertando batch OHLCV: {e}")
        return inserted
    def insert_indicators(self, records):
        if not records: return 0
        inserted = 0
        for i in range(0, len(records), config.EXECUTION["batch_size"]):
            batch = records[i:i + config.EXECUTION["batch_size"]]
            try:
                self.client.table("indicators").upsert(batch, on_conflict="pair,timeframe,timestamp").execute()
                inserted += len(batch)
            except Exception as e:
                logger.error(f"Error insertando indicadores: {e}")
        return inserted
    def insert_signals(self, records):
        if not records: return 0
        try:
            self.client.table("signals").upsert(records, on_conflict="pair,timeframe,timestamp").execute()
            return len(records)
        except Exception as e:
            logger.error(f"Error insertando senales: {e}")
            return 0
    def insert_trade(self, record):
        try:
            result = self.client.table("trades").insert(record).execute()
            return result.data[0]["id"] if result.data else None
        except Exception as e:
            logger.error(f"Error insertando trade: {e}")
            return None
    def update_trade(self, trade_id, updates):
        try:
            self.client.table("trades").update(updates).eq("id", trade_id).execute()
        except Exception as e:
            logger.error(f"Error actualizando trade {trade_id}: {e}")
    def get_open_trades(self):
        try:
            result = self.client.table("trades").select("*").eq("status", "OPEN").execute()
            return result.data or []
        except Exception as e:
            logger.error(f"Error obteniendo trades abiertos: {e}")
            return []
    def get_latest_ohlcv(self, pair, timeframe, limit=200):
        try:
            result = self.client.table("ohlcv").select("*").eq("pair", pair).eq("timeframe", timeframe).order("timestamp", desc=True).limit(limit).execute()
            return list(reversed(result.data)) if result.data else []
        except Exception as e:
            logger.error(f"Error obteniendo OHLCV: {e}")
            return []
    def get_last_timestamp(self, pair, timeframe):
        try:
            result = self.client.table("ohlcv").select("timestamp").eq("pair", pair).eq("timeframe", timeframe).order("timestamp", desc=True).limit(1).execute()
            if result.data:
                ts = result.data[0]["timestamp"]
                if isinstance(ts, str):
                    return datetime.fromisoformat(ts.replace("Z", "+00:00"))
                return ts
        except Exception as e:
            logger.error(f"Error obteniendo ultimo timestamp: {e}")
        return None
    def log(self, level, component, message, details=None):
        if not config.LOG_TO_DB: return
        try:
            self.client.table("bot_logs").insert({"level": level, "component": component, "message": message, "details": details or {}}).execute()
        except Exception:
            pass
    def get_daily_pnl(self):
        try:
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            result = self.client.table("trades").select("pnl").gte("closed_at", today).execute()
            return sum(t.get("pnl") or 0 for t in (result.data or []))
        except Exception:
            return 0.0

class DataValidator:
    @staticmethod
    def validate_candle(candle):
        required = ["open", "high", "low", "close", "volume", "timestamp"]
        for field in required:
            if field not in candle or candle[field] is None:
                return False, f"Campo faltante: {field}"
        o, h, l, c = candle["open"], candle["high"], candle["low"], candle["close"]
        if not (l <= h): return False, f"Low ({l}) > High ({h})"
        if not (l <= o <= h): return False, f"Open ({o}) fuera de rango"
        if not (l <= c <= h): return False, f"Close ({c}) fuera de rango"
        if candle["volume"] < 0: return False, "Volume negativo"
        return True, None
    @staticmethod
    def validate_batch(records):
        valid, invalid = [], []
        for rec in records:
            ok, err = DataValidator.validate_candle(rec)
            if ok: valid.append(rec)
            else: invalid.append({**rec, "_error": err})
        return valid, invalid

class BotCore:
    def __init__(self):
        config.validate_config()
        self.kraken = KrakenClient(config.KRAKEN_API_KEY, config.KRAKEN_API_SECRET)
        self.db = SupabaseStore(config.SUPABASE_URL, config.SUPABASE_KEY)
        self.validator = DataValidator()
    def fetch_and_store(self, pair, timeframe, since=None):
        logger.info(f"📊 Fetching {pair} {config.TF_MAP.get(timeframe, timeframe)} desde Kraken...")
        try:
            raw_candles = self.kraken.get_ohlc(pair, timeframe, since)
        except Exception as e:
            logger.error(f"❌ Error fetching {pair}: {e}")
            self.db.log("ERROR", "BotCore", f"Fetch fallido {pair}", {"error": str(e)})
            return 0
        if not raw_candles:
            logger.warning(f"⚠️ No se recibieron datos para {pair}")
            return 0
        records = []
        for candle in raw_candles:
            ts = datetime.fromtimestamp(candle[0], tz=timezone.utc)
            records.append({
                "pair": pair, "timeframe": timeframe, "timestamp": ts.isoformat(),
                "open": float(candle[1]), "high": float(candle[2]), "low": float(candle[3]),
                "close": float(candle[4]), "volume": float(candle[6]), "trades_count": int(candle[7]),
            })
        valid, invalid = self.validator.validate_batch(records)
        if invalid:
            logger.warning(f"⚠️ {len(invalid)} velas invalidas descartadas")
        inserted = self.db.insert_ohlcv_batch(valid)
        logger.info(f"✅ {pair} {config.TF_MAP.get(timeframe, timeframe)}: {inserted}/{len(records)} velas insertadas")
        self.db.log("INFO", "BotCore", "Backfill completado", {"pair": pair, "timeframe": timeframe, "inserted": inserted, "invalid": len(invalid)})
        return inserted
    def backfill(self, pair, timeframe, days=3):
        logger.info(f"🔄 Backfill {pair} {config.TF_MAP.get(timeframe, timeframe)} — ultimos {days} dias")
        since_ts = int(time.time()) - (days * 24 * 60 * 60)
        total_inserted = 0
        current_since = since_ts
        for _ in range(10):
            inserted = self.fetch_and_store(pair, timeframe, current_since)
            if inserted == 0: break
            total_inserted += inserted
            last_ts = self.db.get_last_timestamp(pair, timeframe)
            if last_ts:
                current_since = int(last_ts.timestamp()) + 1
            else:
                break
            time.sleep(0.5)
        logger.info(f"🔄 Backfill {pair} completado: {total_inserted} velas totales")
        return total_inserted
    def run_pipeline(self, pairs_timeframes, backfill_days=3):
        logger.info("=" * 60)
        logger.info("🚀 INICIANDO PIPELINE DepaFix Bot")
        logger.info("=" * 60)
        total = 0
        for pair, tf in pairs_timeframes:
            try:
                n = self.backfill(pair, tf, backfill_days)
                total += n
                time.sleep(1)
            except Exception as e:
                logger.error(f"❌ Error en pipeline {pair}/{tf}: {e}")
                self.db.log("ERROR", "BotCore", "Pipeline fallido", {"pair": pair, "timeframe": tf, "error": str(e)})
        logger.info("=" * 60)
        logger.info(f"🏁 PIPELINE COMPLETADO: {total} velas insertadas en total")
        logger.info("=" * 60)
        return total

if __name__ == "__main__":
    bot = BotCore()
    bot.run_pipeline(config.PARES_TIMEFRAMES, backfill_days=3)
