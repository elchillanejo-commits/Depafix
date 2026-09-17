"""
02_config.py — Configuración centralizada del bot DepaFix
Todas las variables editables en un solo lugar.
Carga credenciales desde .env (nunca hardcodear secrets)
"""

import os
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
KRAKEN_API_KEY = os.getenv("KRAKEN_API_KEY", "")
KRAKEN_API_SECRET = os.getenv("KRAKEN_API_SECRET", "")

PARES_TIMEFRAMES = [
    ("BTC/USD", 60),
    ("BTC/USD", 240),
    ("ETH/USD", 60),
    ("ETH/USD", 240),
    ("SOL/USD", 60),
    ("XRP/USD", 60),
]

TF_MAP = {
    1: "1m", 5: "5m", 15: "15m", 30: "30m",
    60: "1h", 240: "4h", 1440: "1d", 10080: "1w"
}

INDICATORS = {
    "ema": {"fast": 9, "medium": 21, "slow": 50, "long": 200},
    "rsi": {"period": 14, "overbought": 70, "oversold": 30},
    "macd": {"fast": 12, "slow": 26, "signal": 9},
    "bollinger": {"period": 20, "std_dev": 2.0},
    "atr": {"period": 14},
    "volume": {"sma_period": 20},
}

STRATEGY = {
    "min_score": 50,
    "weights": {
        "ema_trend": 25,
        "rsi_momentum": 20,
        "macd_confirmation": 20,
        "bb_position": 15,
        "volume_spike": 10,
        "multi_tf": 10,
    },
    "rsi_buy_zone": (30, 55),
    "rsi_sell_zone": (65, 85),
    "bb_distance_threshold": 0.3,
}

RISK = {
    "capital_usd": 1000.0,
    "risk_per_trade_pct": 2.0,
    "max_daily_drawdown_pct": 5.0,
    "min_risk_reward_ratio": 2.0,
    "atr_sl_multiplier": 2.0,
    "atr_tp_multiplier": 4.0,
    "max_open_trades": 3,
    "max_exposure_pct": 50.0,
}

PAPER_TRADING = True

EXECUTION = {
    "loop_interval": 60,
    "backfill_limit": 500,
    "batch_size": 100,
    "kraken_timeout": 30,
    "max_retries": 3,
    "retry_delay": 2,
}

LOG_LEVEL = "INFO"
LOG_TO_DB = True
LOG_TO_CONSOLE = True


def validate_config():
    errors = []
    if not SUPABASE_URL:
        errors.append("SUPABASE_URL no esta definido en .env")
    if not SUPABASE_KEY:
        errors.append("SUPABASE_KEY no esta definido en .env")
    if not KRAKEN_API_KEY:
        errors.append("KRAKEN_API_KEY no esta definido en .env")
    if not KRAKEN_API_SECRET:
        errors.append("KRAKEN_API_SECRET no esta definido en .env")
    if errors:
        raise ValueError("\n".join(errors))
    return True
