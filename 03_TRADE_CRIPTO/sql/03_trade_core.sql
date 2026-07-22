-- ============================================================
-- 03_trade_core.sql
-- Dominio TRADE_CRIPTO (core): velas, señales, órdenes, portfolio
-- y mercados activos. Generado a partir del esquema real de
-- Supabase.
--
-- Idempotente: seguro de re-ejecutar contra una base ya poblada.
-- ============================================================

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS velas_cripto (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    par        varchar(20) NOT NULL,
    intervalo  varchar(10) NOT NULL,
    apertura   numeric NOT NULL,
    cierre     numeric NOT NULL,
    maximo     numeric NOT NULL,
    minimo     numeric NOT NULL,
    volumen    numeric NOT NULL,
    "timestamp" timestamptz NOT NULL,
    created_at timestamptz DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_velas_unique ON velas_cripto(par, intervalo, "timestamp");
ALTER TABLE velas_cripto ENABLE ROW LEVEL SECURITY;
-- Cierra el acceso de 'anon' (antes sql/create_bi_readonly.sql). Sin
-- policy para anon a propósito: con RLS activado y cero policies,
-- PostgREST deniega todo acceso a ese rol. data_pipeline.py escribe
-- con SUPABASE_SERVICE_ROLE_KEY (bypassea RLS).
REVOKE ALL ON public.velas_cripto FROM anon;
DROP POLICY IF EXISTS "bi_readonly_access_velas" ON velas_cripto;
CREATE POLICY "bi_readonly_access_velas" ON velas_cripto FOR SELECT TO bi_readonly USING (true);

CREATE TABLE IF NOT EXISTS operaciones_ejecutadas (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol       text NOT NULL,
    price        numeric NOT NULL,
    side         text NOT NULL,
    ejecutada    boolean DEFAULT false,
    hash_control text NOT NULL UNIQUE,
    created_at   timestamptz DEFAULT now()
);
ALTER TABLE operaciones_ejecutadas ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "bi_readonly_access_operaciones" ON operaciones_ejecutadas;
CREATE POLICY "bi_readonly_access_operaciones" ON operaciones_ejecutadas FOR SELECT TO bi_readonly USING (true);

CREATE TABLE IF NOT EXISTS trade_signals (
    id             SERIAL PRIMARY KEY,
    par            varchar(20) NOT NULL,
    "timestamp"    timestamp DEFAULT now(),
    estrategia     varchar(50),
    senal          varchar(10),
    precio_entrada numeric(20,8),
    precio_salida  numeric(20,8),
    resultado      numeric(10,2),
    estado         varchar(20) DEFAULT 'PENDIENTE',
    metadata       jsonb,
    created_at     timestamp DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_signals_par_estado ON trade_signals(par, estado);
ALTER TABLE trade_signals ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Todos pueden leer señales" ON trade_signals;
CREATE POLICY "Todos pueden leer señales" ON trade_signals FOR SELECT USING (true);

CREATE TABLE IF NOT EXISTS trade_orders (
    id                 SERIAL PRIMARY KEY,
    signal_id          integer REFERENCES trade_signals(id) ON DELETE SET NULL,
    par                varchar(20) NOT NULL,
    tipo               varchar(20),
    lado               varchar(10),
    cantidad           numeric(20,8),
    precio             numeric(20,8),
    comision           numeric(20,8),
    estado             varchar(20),
    exchange_order_id  varchar(100),
    fecha_ejecucion    timestamp,
    metadata           jsonb,
    created_at         timestamp DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_orders_par_estado ON trade_orders(par, estado);
CREATE INDEX IF NOT EXISTS idx_orders_signal ON trade_orders(signal_id);
ALTER TABLE trade_orders ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Todos pueden leer órdenes" ON trade_orders;
CREATE POLICY "Todos pueden leer órdenes" ON trade_orders FOR SELECT USING (true);

CREATE TABLE IF NOT EXISTS trade_portfolio (
    id         SERIAL PRIMARY KEY,
    exchange   varchar(50),
    asset      varchar(20),
    cantidad   numeric(20,8),
    valor_usd  numeric(20,2),
    updated_at timestamp DEFAULT now(),
    UNIQUE (exchange, asset)
);
ALTER TABLE trade_portfolio ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Todos pueden leer portfolio" ON trade_portfolio;
CREATE POLICY "Todos pueden leer portfolio" ON trade_portfolio FOR SELECT USING (true);

CREATE TABLE IF NOT EXISTS mercados_activos (
    symbol     text PRIMARY KEY,
    is_active  boolean DEFAULT true,
    min_volume numeric DEFAULT 0,
    last_check timestamptz DEFAULT now()
);
