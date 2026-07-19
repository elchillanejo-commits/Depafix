-- ==================================================
-- 02_reportes_trading
-- Reportes automáticos del agente Trading Siegfried
-- ==================================================

DROP TABLE IF EXISTS reportes_trading CASCADE;

CREATE TABLE reportes_trading (
    id BIGSERIAL PRIMARY KEY,
    tipo TEXT NOT NULL CHECK (tipo IN ('horario', 'diario', 'semanal', 'quincenal', 'mensual')),
    periodo TEXT NOT NULL,
    resumen JSONB,
    detalle JSONB,
    tendencias JSONB,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_reportes_tipo_created ON reportes_trading(tipo, created_at DESC);
CREATE INDEX idx_reportes_periodo ON reportes_trading(periodo);
CREATE INDEX idx_reportes_created ON reportes_trading(created_at);

ALTER TABLE reportes_trading ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'reportes_trading_select_policy') THEN
        CREATE POLICY reportes_trading_select_policy ON reportes_trading
            FOR SELECT USING (true);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'reportes_trading_insert_policy') THEN
        CREATE POLICY reportes_trading_insert_policy ON reportes_trading
            FOR INSERT WITH CHECK (true);
    END IF;
END $$;
