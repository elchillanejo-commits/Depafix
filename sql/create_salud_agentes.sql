-- salud_agentes: heartbeat de salud de los agentes/cron del repo (hoy la
-- escriben trading_orchestrator.py, mercado_publico/multi_dia.py y
-- core/trade_agent.py / procurador/trade_agent.py), para que Siegfried (u
-- otro monitor) sepa si un proceso corrio bien sin tener que entrar al
-- servidor ni parsear logs. Tabla generica (columna `agente`) para que
-- otros agentes puedan reusarla sin una migracion nueva.
--
-- Este archivo documentaba hasta 2026-07-21 un esquema
-- (proceso/detalle/corrido_at, CHECK HEALTHY/CRITICAL) que NO coincidia con
-- la tabla real en Supabase -- diverguieron en algun punto y nadie lo
-- notó hasta que se audito core/salud_agentes.py vs procurador/core/
-- salud_agentes.py. Lo de abajo es el esquema real, confirmado contra
-- information_schema.columns y pg_constraint en vivo (no contra este mismo
-- archivo, para no repetir el error). El código (core/salud_agentes.py,
-- procurador/core/salud_agentes.py) sigue usando 'HEALTHY'/'CRITICAL' como
-- vocabulario semántico y lo traduce a online/error en el único punto de
-- escritura -- no hace falta que ese vocabulario cambie en cada call site.

CREATE TABLE IF NOT EXISTS salud_agentes (
    id BIGSERIAL PRIMARY KEY,
    agente TEXT NOT NULL,
    estado TEXT NOT NULL CHECK (estado IN ('online', 'offline', 'error', 'warning')),
    mensaje TEXT,
    metricas JSONB,
    ultimo_ciclo TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_salud_agentes_lookup
    ON salud_agentes (agente, ultimo_ciclo DESC);

COMMENT ON TABLE salud_agentes IS
    'Heartbeat de salud por agente/proceso (online/offline/error/warning + mensaje + metricas JSONB). Consultar la fila mas reciente por `agente` (ultimo_ciclo DESC) para saber si esta vivo.';

-- Mismo patron de seguridad que alertas_precio_serviu y operaciones_ejecutadas:
-- RLS activado sin policy para anon a proposito. Los agentes escriben con
-- SUPABASE_SERVICE_ROLE_KEY (bypassea RLS). Si Siegfried necesita leer esta
-- tabla vía la key anon (en vez de una conexion directa a Postgres), hay que
-- agregar una policy de SELECT explicita -- no está incluida acá a proposito,
-- para no exponer por defecto una tabla que hoy nadie mas que service_role
-- necesita leer.
ALTER TABLE salud_agentes ENABLE ROW LEVEL SECURITY;
