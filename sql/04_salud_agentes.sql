-- 04_salud_agentes
CREATE TABLE IF NOT EXISTS salud_agentes (
    id BIGSERIAL PRIMARY KEY,
    agente TEXT NOT NULL,
    estado TEXT NOT NULL CHECK (estado IN ('online', 'offline', 'error', 'warning')),
    ultimo_ciclo TIMESTAMPTZ,
    mensaje TEXT,
    metricas JSONB,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_salud_agente_created ON salud_agentes(agente, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_salud_estado ON salud_agentes(estado);
CREATE INDEX IF NOT EXISTS idx_salud_ultimo_ciclo ON salud_agentes(ultimo_ciclo);

ALTER TABLE salud_agentes ENABLE ROW LEVEL SECURITY;

CREATE POLICY salud_agentes_select_policy ON salud_agentes
    FOR SELECT USING (true);

CREATE POLICY salud_agentes_insert_policy ON salud_agentes
    FOR INSERT WITH CHECK (true);
