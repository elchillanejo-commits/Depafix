-- alertas_precio_serviu: auditoria de anomalias de precio detectadas por
-- core/trade_agent.py sobre precios_serviu (SERVIU + Mercado Publico).
-- Mismo patron que operaciones_ejecutadas (sql/create_operaciones_ejecutadas.sql):
-- cada alerta queda con un hash_control (SHA-256 del item + estadisticas del
-- rubro que la motivaron) para poder verificar despues con que datos exactos
-- se genero, sin tener que reconstruir el estado completo de precios_serviu.

CREATE TABLE IF NOT EXISTS alertas_precio_serviu (
    id SERIAL PRIMARY KEY,
    item_id INTEGER,
    item TEXT,
    rubro TEXT NOT NULL,
    valor_clp NUMERIC NOT NULL,
    promedio_rubro_clp NUMERIC NOT NULL,
    desviacion_pct NUMERIC NOT NULL,
    z_score NUMERIC,
    tipo TEXT NOT NULL,
    severidad TEXT NOT NULL,
    n_muestras_rubro INTEGER NOT NULL,
    desde_cache BOOLEAN DEFAULT false,
    hash_control TEXT NOT NULL,
    detectado_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_alertas_precio_serviu_lookup
    ON alertas_precio_serviu (rubro, detectado_at DESC);

COMMENT ON TABLE alertas_precio_serviu IS
    'Auditoria de anomalias de precio detectadas por core/trade_agent.py. hash_control = SHA-256 del item + estadisticas del rubro que motivaron la alerta. desde_cache=true indica que la corrida uso el snapshot local (cache_trade_agent.json) porque Supabase no respondio.';

-- Mismo patron de seguridad que operaciones_ejecutadas y velas_cripto: RLS
-- activado sin policy para anon a proposito. trade_agent.py escribe con
-- SUPABASE_SERVICE_ROLE_KEY (bypassea RLS), asi que la tabla funciona sin
-- exponer escritura/lectura a la key anon, que es publica por diseno.
ALTER TABLE alertas_precio_serviu ENABLE ROW LEVEL SECURITY;
