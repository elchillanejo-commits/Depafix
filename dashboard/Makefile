.PHONY: start stop restart status logs

start:
	@echo "🚀 Iniciando dashboard..."
	@nohup python3 app.py > /tmp/dashboard.log 2>&1 & echo $$! > dashboard.pid
	@echo "✅ Dashboard iniciado (PID: $$(cat dashboard.pid))"
	@sleep 2
	@curl -s http://localhost:5050 > /dev/null && echo "🌐 http://localhost:5050"

stop:
	@echo "🛑 Deteniendo dashboard..."
	@-kill $$(cat dashboard.pid 2>/dev/null) 2>/dev/null || true
	@-rm -f dashboard.pid
	@echo "✅ Dashboard detenido."

restart: stop start

status:
	@if [ -f dashboard.pid ] && kill -0 $$(cat dashboard.pid) 2>/dev/null; then \
		echo "✅ Dashboard corriendo (PID: $$(cat dashboard.pid))"; \
		echo "🌐 http://localhost:5050"; \
	else \
		echo "❌ Dashboard no está corriendo"; \
	fi

logs:
	@tail -f /tmp/dashboard.log
