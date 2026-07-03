#!/bin/bash
echo "--- ESTADO DEL SISTEMA MAQUIAVELO ---"
if pgrep -f "bot_maquiavelo.sh" > /dev/null; then echo "✅ Bot Telegram: ONLINE"; else echo "❌ Bot Telegram: DOWN"; fi
if pgrep -f "ngrok" > /dev/null; then echo "✅ Ngrok Tunnel: ONLINE"; else echo "❌ Ngrok Tunnel: DOWN"; fi
if pgrep -f "http.server" > /dev/null; then echo "✅ Web Server: ONLINE"; else echo "❌ Web Server: DOWN"; fi
