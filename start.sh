#!/bin/bash
set -euo pipefail

if command -v python3 &>/dev/null; then
    PYTHON=python3
elif command -v python &>/dev/null; then
    PYTHON=python
else
    echo "No se encontró Python"
    exit 1
fi

echo "Iniciando DepaFix API con $PYTHON en el puerto ${PORT:-8000}..."
exec "$PYTHON" -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
