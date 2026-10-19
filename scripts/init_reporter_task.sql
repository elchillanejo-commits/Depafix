-- Crear tarea recurrente para el reporter diario (08:00 UTC)
INSERT INTO ceo_tasks (tipo, frecuencia_cron, proxima_ejecucion)
VALUES ('reporter_daily', '0 8 * * *', (DATE_TRUNC('day', NOW() + INTERVAL '1 day') + INTERVAL '8 hours'));
