#!/bin/bash
cd "$(dirname "$0")/.."
source venv/bin/activate

if [ "$1" == "--live" ]; then
    echo "🚀 Modo LIVE (con dinero real)"
    python 05_TRADE_CRIPTO/01_BOT_TRADING.py --live
else
    echo "🧪 Modo DRY-RUN (simulación)"
    python 05_TRADE_CRIPTO/01_BOT_TRADING.py --dry-run
fi
