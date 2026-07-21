CREATE TABLE IF NOT EXISTS operaciones_ejecutadas (
    id SERIAL PRIMARY KEY,
    activo TEXT NOT NULL,
    temporalidad TEXT NOT NULL,
    senal TEXT NOT NULL,
    precio_entrada NUMERIC,
    precio_salida NUMERIC,
    cantidad NUMERIC,
    motivo TEXT,
    hash_control TEXT,
    ejecutada BOOLEAN DEFAULT false,
    timestamp TIMESTAMPTZ DEFAULT now()
);

-- Por si la tabla ya existia sin esta columna (ver TradingOrchestrator,
-- que agrega hash_control = SHA-256 del estado de mercado usado para la
-- senal, para poder verificar despues con que datos exactos se genero).
ALTER TABLE operaciones_ejecutadas ADD COLUMN IF NOT EXISTS hash_control TEXT;

CREATE INDEX IF NOT EXISTS idx_operaciones_ejecutadas_lookup
    ON operaciones_ejecutadas (activo, temporalidad, timestamp DESC);

COMMENT ON TABLE operaciones_ejecutadas IS
    'Auditoria de senales generadas por TradingOrchestrator (src/trading/trading_orchestrator.py). ejecutada=false siempre en este repo: no existe integracion de ordenes reales con ningun exchange, solo simulacion + registro.';

-- Mismo patron de seguridad que velas_cripto (sql/create_velas_cripto.sql):
-- RLS activado sin policy para anon a proposito. TradingOrchestrator escribe
-- con SUPABASE_SERVICE_ROLE_KEY (bypassea RLS), asi que la tabla funciona sin
-- exponer escritura/lectura a la key anon, que es publica por diseno.
ALTER TABLE operaciones_ejecutadas ENABLE ROW LEVEL SECURITY;
