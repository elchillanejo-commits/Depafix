-- La tabla operaciones_ejecutadas en Supabase quedo creada a mano (via
-- dashboard) ANTES de que existiera sql/create_operaciones_ejecutadas.sql,
-- con un esquema minimo (id uuid, symbol, price, hash_control, ejecutada)
-- que nunca se reconcilio -- ese SQL nunca se corrio contra la base real.
-- Verificado 2026-07-18: TradingOrchestrator._registrar_operacion (src/
-- trading/trading_orchestrator.py) inserta con columnas activo/temporalidad/
-- senal/precio_entrada/precio_salida/cantidad/motivo/timestamp, NINGUNA de
-- las cuales existe en la tabla real -- cada INSERT de una señal COMPRA/
-- VENTA real fallaba en silencio (PGRST204, atrapado por el fail-safe de
-- red_segura como si fuera un problema de red transitorio).
--
-- Este ALTER agrega las columnas que el codigo realmente necesita, sin
-- tocar symbol/price/id/ejecutada (nada mas en el repo las usa, pero
-- borrarlas es innecesariamente destructivo para lo que se gana).

ALTER TABLE operaciones_ejecutadas ADD COLUMN IF NOT EXISTS activo TEXT;
ALTER TABLE operaciones_ejecutadas ADD COLUMN IF NOT EXISTS temporalidad TEXT;
ALTER TABLE operaciones_ejecutadas ADD COLUMN IF NOT EXISTS senal TEXT;
ALTER TABLE operaciones_ejecutadas ADD COLUMN IF NOT EXISTS precio_entrada NUMERIC;
ALTER TABLE operaciones_ejecutadas ADD COLUMN IF NOT EXISTS precio_salida NUMERIC;
ALTER TABLE operaciones_ejecutadas ADD COLUMN IF NOT EXISTS cantidad NUMERIC;
ALTER TABLE operaciones_ejecutadas ADD COLUMN IF NOT EXISTS motivo TEXT;
ALTER TABLE operaciones_ejecutadas ADD COLUMN IF NOT EXISTS "timestamp" TIMESTAMPTZ DEFAULT now();

CREATE INDEX IF NOT EXISTS idx_operaciones_ejecutadas_lookup
    ON operaciones_ejecutadas (activo, temporalidad, "timestamp" DESC);

-- report_generator.py filtra por rango de fecha sobre esta columna
-- (gte/lt "timestamp") para armar los reportes horario/diario/semanal/
-- quincenal/mensual -- sin el DEFAULT now(), las filas insertadas por
-- TradingOrchestrator (que no manda timestamp explicito) quedarian NULL y
-- quedarian fuera de cualquier rango de fecha.
