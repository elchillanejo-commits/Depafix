#!/bin/bash
if command -v python3 &>/dev/null; then
    PYTHON=python3
elif command -v python &>/dev/null; then
    PYTHON=python
else
    echo "❌ No se encontró Python"
    exit 1
fi
echo "🔍 Iniciando con $PYTHON..."
$PYTHON -u dashboard_trading.py monitorear 300 75000 73000 2>&1
