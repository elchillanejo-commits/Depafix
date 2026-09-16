-- Agrega columna para persistir el order id devuelto por el exchange (ccxt)
-- al ejecutar una orden real en trading_orchestrator.py.
ALTER TABLE operaciones_ejecutadas ADD COLUMN IF NOT EXISTS orden_id text;
