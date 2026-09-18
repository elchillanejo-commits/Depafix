CREATE TABLE IF NOT EXISTS ceo_tasks (
    id SERIAL PRIMARY KEY,
    tipo TEXT NOT NULL,              -- 'scrape_sodimac', 'find_leads', 'monitor_bot'
    parametros JSONB DEFAULT '{}',   -- {query, region, ...}
    schedule TEXT,                   -- cron expr, NULL = on-demand
    estado TEXT DEFAULT 'pending',   -- pending, running, done, failed
    resultado JSONB,
    error TEXT,
    creado_en TIMESTAMPTZ DEFAULT NOW(),
    ejecutado_en TIMESTAMPTZ,
    proxima_ejecucion TIMESTAMPTZ,
    duracion_ms INTEGER
);
CREATE INDEX idx_ceo_tasks_proxima ON ceo_tasks (proxima_ejecucion) WHERE estado = 'pending';
CREATE INDEX idx_ceo_tasks_tipo ON ceo_tasks (tipo);

CREATE TABLE IF NOT EXISTS ceo_results (
    id SERIAL PRIMARY KEY,
    task_id INTEGER REFERENCES ceo_tasks(id) ON DELETE CASCADE,
    datos JSONB,
    creado_en TIMESTAMPTZ DEFAULT NOW()
);
