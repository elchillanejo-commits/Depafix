# Ingeniero - Health Check

Este módulo realiza chequeos automáticos del estado de DepaFix.

## Chequeos
- `bot_service`: Verifica si `depafix-trading.service` está activo.
- `postgres_container`: Verifica si el contenedor `core-postgres` está corriendo.
- `supabase_db`: Verifica disponibilidad y frescura de los datos en `velas_cripto`.
- `error_logs`: Cuenta errores en `logs/trading_systemd.log`.

## Configuración
Se ejecuta cada 15 minutos mediante `systemd timer`.
Logs: `ingeniero/health.log` (rotación automática).

## Comandos
- Ejecución manual: `python3 ingeniero/health_check.py`
- Status del timer: `systemctl --user status ingeniero.timer`
