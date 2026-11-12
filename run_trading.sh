#!/bin/bash
cd ~/DepaFix_Maestro
source .venv/bin/activate
set -a
source .env
set +a
python3 bot_trading.py "$@"
