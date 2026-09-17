-- ============================================
-- MIGRACIÓN 01: BASE DE DATOS - LICITACIONES
-- ============================================

-- Tabla de control de migraciones
CREATE TABLE IF NOT EXISTS migrations_log (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    migration_name TEXT NOT NULL UNIQUE,
    executed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    status TEXT DEFAULT 'success'
);

-- Tabla principal de licitaciones
CREATE TABLE IF NOT EXISTS licitaciones (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    codigo_licitacion TEXT UNIQUE NOT NULL,
    titulo TEXT,
    organismo TEXT,
    fecha_publicacion DATE,
    fecha_cierre DATE,
    estado TEXT,
    descripcion TEXT,
    palabras_clave JSONB DEFAULT '[]'::jsonb,
    idempotency_key TEXT UNIQUE,
    monto_estimado NUMERIC(15,2),
    region TEXT,
    comuna TEXT,
    unidad_compra TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE licitaciones IS 'Licitaciones públicas de ChileCompra';
COMMENT ON COLUMN licitaciones.codigo_licitacion IS 'Código único de la licitación';
COMMENT ON COLUMN licitaciones.palabras_clave IS 'Palabras clave extraídas automáticamente';

INSERT INTO migrations_log (migration_name, status) 
VALUES ('01_base', 'success')
ON CONFLICT (migration_name) DO NOTHING;
