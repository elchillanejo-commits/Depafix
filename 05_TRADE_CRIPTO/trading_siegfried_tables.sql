-- ============================================================
-- TRADING SIEGFRIED — Tablas completas
-- Proyecto: DepaFix
-- Base de datos: Supabase (PostgreSQL 15+)
-- Ejecutar: SQL Editor → New query → pegar todo → Run
--
-- Este script es idempotente: puede re-ejecutarse sin errores.
-- Hace DROP CASCADE para limpiar migraciones previas rotas.
-- ============================================================

-- ============================================================
-- 0. LIMPIEZA (elimina tablas si existen con schema incorrecto)
-- ============================================================
DROP TABLE IF EXISTS salud_agentes        CASCADE;
DROP TABLE IF EXISTS reportes_trading     CASCADE;
DROP TABLE IF EXISTS operaciones_ejecutadas CASCADE;
DROP TABLE IF EXISTS velas_cripto         CASCADE;


-- ============================================================
-- 1. velas_cripto
--    OHLCV por activo y temporalidad. Fuente: Kraken / Binance.
-- ============================================================
CREATE TABLE velas_cripto (
    id            SERIAL       PRIMARY KEY,
    activo        TEXT         NOT NULL,
    temporalidad  TEXT         NOT NULL,   -- '1H' | '4H' | '1D'
    tiempo        TIMESTAMPTZ  NOT NULL,   -- apertura de la vela
    open          DOUBLE PRECISION NOT NULL,
    high          DOUBLE PRECISION NOT NULL,
    low           DOUBLE PRECISION NOT NULL,
    close         DOUBLE PRECISION NOT NULL,
    volume        DOUBLE PRECISION,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT now(),
    UNIQUE (activo, temporalidad, tiempo)
);

CREATE INDEX idx_velas_cripto_lookup
    ON velas_cripto (activo, temporalidad, tiempo DESC);

ALTER TABLE velas_cripto ENABLE ROW LEVEL SECURITY;

COMMENT ON TABLE velas_cripto IS
    'Velas OHLCV por activo/temporalidad. '
    'Consumida por src/trading/crypto_trader_agent.py::TradingLogic. '
    'Escrita con service_role key (bypassea RLS).';


-- ============================================================
-- 2. operaciones_ejecutadas
--    Señales de trading (COMPRA/VENTA). No ejecuta órdenes reales.
-- ============================================================
CREATE TABLE operaciones_ejecutadas (
    id             SERIAL       PRIMARY KEY,
    activo         TEXT         NOT NULL,
    temporalidad   TEXT         NOT NULL,
    senal          TEXT         NOT NULL,   -- 'COMPRA' | 'VENTA' | 'ESPERA'
    precio_entrada NUMERIC(20,8),
    precio_salida  NUMERIC(20,8),
    cantidad       NUMERIC(20,8),
    motivo         TEXT,
    hash_control   TEXT,
    ejecutada      BOOLEAN      NOT NULL DEFAULT false,
    timestamp      TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE INDEX idx_operaciones_ejecutadas_lookup
    ON operaciones_ejecutadas (activo, temporalidad, timestamp DESC);

CREATE INDEX idx_operaciones_ejecutadas_senal
    ON operaciones_ejecutadas (senal, timestamp DESC);

ALTER TABLE operaciones_ejecutadas ENABLE ROW LEVEL SECURITY;

COMMENT ON TABLE operaciones_ejecutadas IS
    'Auditoría de señales de TradingOrchestrator. '
    'ejecutada=false siempre: sin integración de órdenes reales. '
    'hash_control = SHA-256 del estado de mercado que generó la señal.';


-- ============================================================
-- 3. reportes_trading
--    Reportes periódicos generados por report_generator.py
-- ============================================================
CREATE TABLE reportes_trading (
    id         SERIAL      PRIMARY KEY,
    tipo       TEXT        NOT NULL,   -- 'horario' | 'diario' | 'semanal' | 'quincenal' | 'mensual'
    periodo    TEXT        NOT NULL,   -- ISO timestamp de cierre de la ventana
    resumen    JSONB,
    detalle    JSONB,
    tendencias JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_reportes_trading_tipo_fecha
    ON reportes_trading (tipo, created_at DESC);

ALTER TABLE reportes_trading ENABLE ROW LEVEL SECURITY;

COMMENT ON TABLE reportes_trading IS
    'Reportes periódicos de trading. '
    'Generados por src/trading/report_generator.py dentro del ciclo de trading_orchestrator.py.';


-- ============================================================
-- 4. salud_agentes
--    Heartbeat HEALTHY/CRITICAL de cada agente/proceso
-- ============================================================
CREATE TABLE salud_agentes (
    id         SERIAL      PRIMARY KEY,
    proceso    TEXT        NOT NULL,
    estado     TEXT        NOT NULL CHECK (estado IN ('HEALTHY', 'CRITICAL')),
    detalle    TEXT,
    metricas   JSONB,
    corrido_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_salud_agentes_lookup
    ON salud_agentes (proceso, corrido_at DESC);

ALTER TABLE salud_agentes ENABLE ROW LEVEL SECURITY;

COMMENT ON TABLE salud_agentes IS
    'Heartbeat por proceso (HEALTHY/CRITICAL). '
    'Consultar la fila más reciente por proceso para saber si está vivo.';


-- ============================================================
-- 5. VERIFICACIÓN — ejecutar después del bloque anterior
-- ============================================================
SELECT
    table_name,
    (SELECT count(*) FROM information_schema.columns c
     WHERE c.table_name = t.table_name AND c.table_schema = 'public') AS columnas
FROM information_schema.tables t
WHERE table_schema = 'public'
  AND table_name IN ('velas_cripto','operaciones_ejecutadas','reportes_trading','salud_agentes')
ORDER BY table_name;
