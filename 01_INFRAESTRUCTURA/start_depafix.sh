#!/bin/bash
cd ~/Proyectos/DepaFix
export PYTHONPATH=$PWD:$PYTHONPATH
fuser -k 8000/tcp 2>/dev/null
sleep 1
echo "🚀 Iniciando DepaFix en puerto 8000..."
uvicorn core.main:app --host 0.0.0.0 --port 8000 --log-level info
