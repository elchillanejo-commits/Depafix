-- salud_agentes: heartbeat de salud de los agentes/cron del repo (hoy solo
-- lo escribe core/trade_agent.py), para que Siegfried (u otro monitor) sepa
-- si un proceso corrio bien sin tener que entrar al servidor ni parsear
-- logs. Tabla generica (columna `proceso`) para que otros agentes puedan
-- reusarla sin una migracion nueva.

CREATE TABLE IF NOT EXISTS salud_agentes (
    id SERIAL PRIMARY KEY,
    proceso TEXT NOT NULL,
    estado TEXT NOT NULL CHECK (estado IN ('HEALTHY', 'CRITICAL')),
    detalle TEXT,
    metricas JSONB,
    corrido_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_salud_agentes_lookup
    ON salud_agentes (proceso, corrido_at DESC);

COMMENT ON TABLE salud_agentes IS
    'Heartbeat de salud por proceso/agente (HEALTHY/CRITICAL + detalle + metricas JSONB). Consultar la fila mas reciente por `proceso` para saber si esta vivo.';

-- Mismo patron de seguridad que alertas_precio_serviu y operaciones_ejecutadas:
-- RLS activado sin policy para anon a proposito. Los agentes escriben con
-- SUPABASE_SERVICE_ROLE_KEY (bypassea RLS). Si Siegfried necesita leer esta
-- tabla vía la key anon (en vez de una conexion directa a Postgres), hay que
-- agregar una policy de SELECT explicita -- no está incluida acá a proposito,
-- para no exponer por defecto una tabla que hoy nadie mas que service_role
-- necesita leer.
ALTER TABLE salud_agentes ENABLE ROW LEVEL SECURITY;
