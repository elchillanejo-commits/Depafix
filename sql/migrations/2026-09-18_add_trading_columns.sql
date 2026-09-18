-- Migración: agregar columnas de auditoría a operaciones_ejecutadas
-- Fecha: 2026-09-18
-- Autor: DepaFix (integración refactor v2)
--
-- Contexto: el adapter crypto_trader_agent.py envía 3 campos nuevos
-- que Supabase ignora porque las columnas no existen:
--   - stop_loss           (precio técnico de salida)
--   - take_profit_1       (primer objetivo para tomar 50%)
--   - confluencia_detalle (JSONB array de strings para auditoría)
--
-- Las columnas son NULLABLE para no romper filas existentes.

ALTER TABLE operaciones_ejecutadas
    ADD COLUMN IF NOT EXISTS stop_loss NUMERIC;

ALTER TABLE operaciones_ejecutadas
    ADD COLUMN IF NOT EXISTS take_profit_1 NUMERIC;

ALTER TABLE operaciones_ejecutadas
    ADD COLUMN IF NOT EXISTS confluencia_detalle JSONB;

-- Índice para consultas de auditoría por confluencia
CREATE INDEX IF NOT EXISTS idx_operaciones_confluencia
    ON operaciones_ejecutadas USING GIN (confluencia_detalle);

COMMENT ON COLUMN operaciones_ejecutadas.stop_loss IS
    'Precio técnico de salida (swing low/high del refactor v2)';

COMMENT ON COLUMN operaciones_ejecutadas.take_profit_1 IS
    'Primer objetivo de ganancia (RR 1.5 aplicado a stop_loss)';

COMMENT ON COLUMN operaciones_ejecutadas.confluencia_detalle IS
    'Array JSONB de factores que activaron la señal (auditoría)';
