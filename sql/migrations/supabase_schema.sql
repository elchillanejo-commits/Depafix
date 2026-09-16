-- ============================================================
-- Schema del ledger inmutable en Supabase.
-- Refleja el estado REAL desplegado en producción (proyecto
-- gylyzcjkswltwpouktbi), verificado por introspección directa
-- (information_schema / pg_catalog) el 2026-07-12.
--
-- Tablas de otros subsistemas (usuarios, tokens, consultas,
-- presupuestos) NO están aquí: usuarios/tokens/consultas viven
-- en create_tokens_tables.sql y presupuestos es la réplica de
-- la base de Aquiles; no forman parte del dominio "records".
-- ============================================================

-- ============================================================
-- 1. Habilitar extensiones necesarias
-- ============================================================
CREATE EXTENSION IF NOT EXISTS "pgcrypto";   -- para digest()/SHA-256
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";  -- para UUID

-- ============================================================
-- 2. Tabla de claves públicas de usuarios (PKI)
-- ============================================================
CREATE TABLE IF NOT EXISTS user_keys (
    user_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    public_key TEXT NOT NULL,            -- PEM o base64
    algorithm TEXT NOT NULL DEFAULT 'RSA',
    created_at TIMESTAMPTZ DEFAULT NOW()
    -- NOTA: no tiene updated_at en producción (a diferencia de una versión anterior de este archivo).
);

-- ============================================================
-- 3. Tabla principal de registros inmutables
-- ============================================================
CREATE TABLE IF NOT EXISTS records (
    record_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content_hash TEXT NOT NULL,
    raw_payload JSONB NOT NULL,
    idempotency_key TEXT UNIQUE NOT NULL,   -- garantiza idempotencia
    created_at TIMESTAMPTZ DEFAULT NOW()
    -- NOTA: en producción esta tabla NO tiene user_id, data, updated_at
    -- ni deleted_at. Usa record_id (no "id") como PK, content_hash y
    -- raw_payload (no "data") como columnas de payload.
);

-- ============================================================
-- 4. Partidas / ítems asociados a un record
-- ============================================================
CREATE TABLE IF NOT EXISTS line_items (
    line_item_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    record_id UUID REFERENCES records(record_id) ON DELETE CASCADE,
    cantidad NUMERIC NOT NULL,
    material TEXT NOT NULL,
    precio_unitario NUMERIC NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- 5. Estudios / firmas (sin relación FK activa por ahora)
-- ============================================================
CREATE TABLE IF NOT EXISTS law_firms (
    firm_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL
);

-- ============================================================
-- 6. Cadena de auditoría (audit_chain)
-- ============================================================
CREATE TABLE IF NOT EXISTS audit_chain (
    event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    record_id UUID REFERENCES records(record_id),
    event_type TEXT NOT NULL,
    event_hash TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
    -- NOTA: en producción NO existen previous_hash ni data_snapshot;
    -- el encadenamiento real es más simple que en una versión anterior
    -- de este archivo (ver enforce_chain_hash() más abajo).
);

-- ============================================================
-- 7. Función + trigger: hash de cada evento en audit_chain
-- ============================================================
CREATE OR REPLACE FUNCTION enforce_chain_hash()
RETURNS TRIGGER AS $function$
begin
  new.event_hash := encode(digest(new.record_id::text || new.event_type, 'sha256'), 'hex');
  return new;
end;
$function$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_hash ON audit_chain;
CREATE TRIGGER trg_hash
BEFORE INSERT ON audit_chain
FOR EACH ROW EXECUTE FUNCTION enforce_chain_hash();

-- ============================================================
-- 8. Índices
-- ============================================================
-- No hay índices adicionales en producción sobre estas tablas: los únicos
-- índices existentes son los implícitos de las PRIMARY KEY y de
-- records_idempotency_key_key (UNIQUE), ya creados arriba.
