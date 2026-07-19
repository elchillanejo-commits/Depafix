-- 03_reportes_trading
CREATE TABLE IF NOT EXISTS reportes_trading (
    id BIGSERIAL PRIMARY KEY,
    tipo TEXT NOT NULL CHECK (tipo IN ('horario', 'diario', 'semanal', 'quincenal', 'mensual')),
    periodo TEXT NOT NULL,
    resumen JSONB,
    detalle JSONB,
    tendencias JSONB,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_reportes_tipo_created ON reportes_trading(tipo, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_reportes_periodo ON reportes_trading(periodo);
CREATE INDEX IF NOT EXISTS idx_reportes_created ON reportes_trading(created_at);

ALTER TABLE reportes_trading ENABLE ROW LEVEL SECURITY;

CREATE POLICY reportes_trading_select_policy ON reportes_trading
    FOR SELECT USING (true);

CREATE POLICY reportes_trading_insert_policy ON reportes_trading
    FOR INSERT WITH CHECK (true);
