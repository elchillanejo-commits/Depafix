#!/bin/bash
# start_trading.sh - Inicia el orquestador de trading en segundo plano

cd /home/ibar/Proyectos/DepaFix
source venv/bin/activate

case "$1" in
  start)
    echo "🚀 Iniciando Trading Orchestrator (BTC/USDT, SOL/USDT)..."
    nohup python3 src/trading/trading_orchestrator.py \
      --exchange kraken \
      --activos BTC/USDT,SOL/USDT \
      --intervalo 300 \
      --una-vez \
      > logs/trading_orchestrator.log 2>&1 &
    echo $! > logs/trading_orchestrator.pid
    echo "Iniciado (PID $(cat logs/trading_orchestrator.pid)). Logs en logs/trading_orchestrator.log"
    ;;
  stop)
    if [ -f logs/trading_orchestrator.pid ]; then
      kill -TERM $(cat logs/trading_orchestrator.pid) 2>/dev/null
      rm -f logs/trading_orchestrator.pid
      echo "Detenido."
    else
      echo "No estaba corriendo (PID file no encontrado)."
    fi
    ;;
  status)
    if [ -f logs/trading_orchestrator.pid ] && kill -0 $(cat logs/trading_orchestrator.pid) 2>/dev/null; then
      echo "Corriendo (PID $(cat logs/trading_orchestrator.pid))."
    else
      echo "Detenido."
    fi
    ;;
  *)
    echo "Uso: $0 {start|stop|status}"
    ;;
esac
