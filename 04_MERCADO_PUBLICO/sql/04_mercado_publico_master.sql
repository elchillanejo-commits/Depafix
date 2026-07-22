-- ============================================================
-- 04_mercado_publico_master.sql
-- Dominio MERCADO_PUBLICO.
--
-- En el esquema real de Supabase NO existe todavía una tabla de
-- catálogo/licitaciones de Mercado Público (ver memoria de
-- proyecto: el scraping de Mercado Público es enriquecimiento
-- posterior a los presupuestos históricos, y aún no se ha
-- desplegado). La única tabla existente relacionada es
-- scrapers_logs, que registra las corridas de scrapers
-- (incluido el de Mercado Público).
--
-- Idempotente: seguro de re-ejecutar contra una base ya poblada.
-- ============================================================

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS scrapers_logs (
    id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    scraper_nombre        text NOT NULL,
    fecha_inicio          timestamptz NOT NULL,
    fecha_fin             timestamptz,
    estado                text NOT NULL CHECK (estado IN ('exito', 'fallo')),
    registros_procesados  integer NOT NULL DEFAULT 0 CHECK (registros_procesados >= 0),
    CONSTRAINT chk_fin_posterior_inicio CHECK (fecha_fin IS NULL OR fecha_fin >= fecha_inicio)
);
CREATE INDEX IF NOT EXISTS idx_scrapers_logs_estado ON scrapers_logs(estado);
CREATE INDEX IF NOT EXISTS idx_scrapers_logs_fecha_inicio ON scrapers_logs(fecha_inicio DESC);
CREATE INDEX IF NOT EXISTS idx_scrapers_logs_nombre ON scrapers_logs(scraper_nombre);
