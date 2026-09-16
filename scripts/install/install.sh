#!/bin/bash
set -e
PY_VERSION=$(python3 --version 2>&1 | grep -oP '(?<=Python )\d+\.\d+')
if [[ $(echo -e "$PY_VERSION\n3.10" | sort -V | head -n1) != "3.10" ]]; then
    echo "❌ Python >=3.10 requerido. Tienes $PY_VERSION"
    exit 1
fi
echo "✅ Python $PY_VERSION"
pip install --upgrade pip
pip install -r requirements.txt
echo "✅ Instalación completada."
