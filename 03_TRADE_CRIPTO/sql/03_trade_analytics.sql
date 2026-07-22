-- ============================================================
-- 03_trade_analytics.sql
-- Dominio TRADE_CRIPTO (analytics): reportes, análisis técnico,
-- métricas on-chain, estrategias/backtests y vistas BI.
-- Generado a partir del esquema real de Supabase.
--
-- Requiere 03_trade_core.sql aplicado antes (vista sobre
-- operaciones_ejecutadas).
--
-- Idempotente: seguro de re-ejecutar contra una base ya poblada.
-- ============================================================

CREATE TABLE IF NOT EXISTS reportes_trading (
    id         bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    tipo       text NOT NULL CHECK (tipo IN ('horario', 'diario', 'semanal', 'quincenal', 'mensual')),
    periodo    text NOT NULL,
    resumen    jsonb,
    detalle    jsonb,
    tendencias jsonb,
    created_at timestamptz DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_reportes_created ON reportes_trading(created_at);
CREATE INDEX IF NOT EXISTS idx_reportes_periodo ON reportes_trading(periodo);
CREATE INDEX IF NOT EXISTS idx_reportes_tipo_created ON reportes_trading(tipo, created_at DESC);
ALTER TABLE reportes_trading ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "reportes_trading_insert_policy" ON reportes_trading;
CREATE POLICY "reportes_trading_insert_policy" ON reportes_trading FOR INSERT WITH CHECK (true);
DROP POLICY IF EXISTS "reportes_trading_select_policy" ON reportes_trading;
CREATE POLICY "reportes_trading_select_policy" ON reportes_trading FOR SELECT USING (true);

CREATE TABLE IF NOT EXISTS analisis_trading (
    id                  SERIAL PRIMARY KEY,
    activo              text NOT NULL,
    temporalidad        text,
    tipo_estructura     text,
    precio_entrada      numeric,
    precio_stop_loss    numeric,
    precio_take_profit  numeric,
    confluencias        jsonb,
    "timestamp"         timestamptz,
    created_at          timestamptz DEFAULT now()
);
ALTER TABLE analisis_trading ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "analisis_trading_insert" ON analisis_trading;
CREATE POLICY "analisis_trading_insert" ON analisis_trading FOR INSERT TO anon, authenticated WITH CHECK (true);
DROP POLICY IF EXISTS "analisis_trading_select" ON analisis_trading;
CREATE POLICY "analisis_trading_select" ON analisis_trading FOR SELECT TO anon, authenticated USING (true);

CREATE TABLE IF NOT EXISTS btc_analysis (
    id                SERIAL PRIMARY KEY,
    metric_category   varchar(50),
    metric_name       varchar(100),
    metric_value      text,
    metric_numeric    numeric(20,4),
    unit              varchar(20),
    context           text,
    source_timestamp  timestamp DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS solana_analysis (
    id                SERIAL PRIMARY KEY,
    metric_category   varchar(50),
    metric_name       varchar(100),
    metric_value      text,
    metric_numeric    numeric(20,4),
    unit              varchar(20),
    context           text,
    source_timestamp  timestamp DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS trade_strategies (
    id          SERIAL PRIMARY KEY,
    nombre      varchar(50) UNIQUE,
    descripcion text,
    parametros  jsonb,
    activa      boolean DEFAULT true,
    created_at  timestamp DEFAULT now()
);
ALTER TABLE trade_strategies ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Todos pueden leer estrategias" ON trade_strategies;
CREATE POLICY "Todos pueden leer estrategias" ON trade_strategies FOR SELECT USING (true);

CREATE TABLE IF NOT EXISTS trade_backtests (
    id                  SERIAL PRIMARY KEY,
    estrategia_id       integer REFERENCES trade_strategies(id),
    par                 varchar(20),
    fecha_inicio        date,
    fecha_fin           date,
    rendimiento_total   numeric(10,2),
    sharpe_ratio        numeric(10,2),
    max_drawdown        numeric(10,2),
    numero_operaciones  integer,
    win_rate            numeric(5,2),
    metadata            jsonb,
    created_at          timestamp DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_backtests_estrategia ON trade_backtests(estrategia_id);
ALTER TABLE trade_backtests ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Todos pueden leer backtests" ON trade_backtests;
CREATE POLICY "Todos pueden leer backtests" ON trade_backtests FOR SELECT USING (true);

CREATE TABLE IF NOT EXISTS tendencias_observadas (
    id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    activo        text NOT NULL,
    temporalidad  text NOT NULL,
    tendencia     text NOT NULL,
    soporte       numeric,
    resistencia   numeric,
    ma_7          numeric,
    ma_25         numeric,
    ma_99         numeric,
    observado_en  timestamptz DEFAULT now(),
    created_at    timestamptz DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_tendencias_activo ON tendencias_observadas(activo, created_at DESC);

CREATE OR REPLACE VIEW vista_reporte_bi AS
SELECT id, symbol, price, side, ejecutada, hash_control, created_at
FROM operaciones_ejecutadas
WHERE ejecutada = true;
