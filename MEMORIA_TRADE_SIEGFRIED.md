# Memoria de control — Sistema de Trading (Siegfried)

Generado el 2026-07-19 como punto de control antes de hacer cambios. Todo lo listado abajo fue verificado contra el código y Supabase en vivo en el momento de escribir esto — no es una descripción aspiracional del sistema, sino su estado real confirmado.

(Nota: reemplaza una versión anterior de este archivo que quedó como una plantilla de shell sin ejecutar — tenía literalmente `$(date ...)`, `$(railway status ...)` y bloques de Python como texto, no datos reales.)

## Fecha de inicio del agente

No hay un "start date" de proceso porque `trading_orchestrator.py` es batch, no un daemon: corre un ciclo y termina (ver `Dockerfile.worker`). No tiene sentido un uptime. Como proxy: el commit que introdujo el pipeline actual (`trading_orchestrator.py` + Kraken + guardado en Supabase) es `6ba6d05`, del 2026-07-16.

## Activos monitoreados

**BTC/USDT, SOL/USDT** — confirmado en `start_trading.sh` y `Dockerfile.worker` (`--activos BTC/USDT,SOL/USDT`), exchange Kraken.

## Modo actual

**Simulación — y no es solo una bandera activada, es lo único que existe.** `trading_orchestrator.py` línea 224 fija `"ejecutada": False` de forma incondicional, con el comentario explícito "no hay integración de órdenes reales en este repo". No hay un modo real implementado para activar; "activar modo real" (ver más abajo) significaría construir esa integración desde cero, no cambiar un flag.

## Estado del worker en Railway

**No verificable desde este entorno** — no tengo acceso a la API/dashboard de Railway desde acá. Como proxy indirecto: la tabla `salud_agentes` (donde el worker debería dejar un heartbeat por ciclo, ver `core/salud_agentes.py`) tiene **0 filas**. Si el worker estuviera corriendo en Railway con el cron configurado, esperaría ver heartbeats recientes ahí. Su ausencia sugiere que no ha corrido en producción todavía (o que la tabla fue recreada recientemente y perdió el historial — este repo tuvo varios resets de tablas durante la sesión de hoy, ver `error_logs`/`compliance_logs`).

## Últimas señales generadas

**Ninguna registrada.** `operaciones_ejecutadas` (donde se auditan señales COMPRA/VENTA accionables — ESPERA deliberadamente no se guarda fila por fila, ver docstring de `report_generator.py`) tiene **0 filas**. No hay evidencia de que el pipeline haya corrido contra datos reales todavía.

## Configuración de reportes automáticos

- Sin scheduler propio: `report_generator.py` se apoya en el mismo ciclo batch de Railway Cron (~cada 5 min) como "tick"; cuando corre, `generar_reportes_vencidos()` mira en la tabla `reportes_trading` cuándo fue la última corrida de cada tipo (horario/diario/semanal/quincenal/mensual) y genera los que ya vencieron.
- Estado persistido en Supabase (`reportes_trading`), no en disco local — necesario porque el contenedor es batch y no sobrevive entre corridas.
- Alertas: `enviar_alerta()` siempre loguea; además envía por Telegram si `TELEGRAM_BOT_TOKEN` y `TELEGRAM_CHAT_ID` están seteados. **Verificado: ninguna de las dos variables está en `.env` ahora mismo** — el canal Telegram no está activo, solo logging.
- `reportes_trading` tiene **0 filas**: nunca se generó un reporte todavía.

## Próximos pasos planeados

Esto es lo que planteás vos, no algo que yo pueda confirmar como "en curso" — lo dejo como lista de pendientes, no de hechos:

1. Confirmar si el worker está desplegado en Railway y con qué Cron Schedule (no verificable desde acá).
2. Configurar `TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID` si se quieren alertas fuera de los logs.
3. Dejar correr al menos un ciclo real contra Kraken para tener la primera fila en `salud_agentes` y confirmar telemetría end-to-end.
4. Activar modo real: requiere diseñar e implementar la integración de órdenes reales (no existe hoy), no solo cambiar una config.
