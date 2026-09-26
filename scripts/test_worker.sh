#!/bin/bash
# test_worker.sh — Prueba un worker localmente sin afectar producción
# Uso: ./scripts/test_worker.sh <nombre_worker> '<json_params>'
#
# Ejemplo:
#   ./scripts/test_worker.sh noop '{}'
#   ./scripts/test_worker.sh monitor_bot '{"horas":2}'

WORKER=$1
PARAMS=${2:-'{}'}

if [ -z "$WORKER" ]; then
    echo "Uso: ./scripts/test_worker.sh <worker> '<json_params>'"
    echo ""
    echo "Workers disponibles:"
    PYTHONPATH=$PWD ./venv/bin/python3 -c "from ceo.workers import WORKERS; [print(f'  - {k}') for k in WORKERS]"
    exit 1
fi

echo "═══════════════════════════════════════════════════════"
echo "🧪 TEST LOCAL: $WORKER"
echo "📦 Params: $PARAMS"
echo "═══════════════════════════════════════════════════════"
echo ""

PYTHONPATH=$PWD ./venv/bin/python3 <<PYEOF
import asyncio
import json
import sys

from ceo.workers import WORKERS

worker = "$WORKER"
params = json.loads('''$PARAMS''')

if worker not in WORKERS:
    print(f"❌ Worker '{worker}' no existe")
    print(f"   Disponibles: {list(WORKERS.keys())}")
    sys.exit(1)

try:
    result = asyncio.run(WORKERS[worker](params))
    print("✅ Resultado:")
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
except Exception as e:
    print(f"❌ Error: {type(e).__name__}: {e}")
    sys.exit(1)
PYEOF
