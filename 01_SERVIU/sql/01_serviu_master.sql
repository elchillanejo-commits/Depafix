-- ============================================================
-- 01_serviu_master.sql
-- Dominio SERVIU: decretos, materiales, precios, rubros contables
-- y la cadena de auditoría (records/audit_chain) de la que depende
-- line_items. Generado a partir del esquema real de Supabase
-- (pg_catalog / information_schema), no de los .sql sueltos previos.
--
-- Dependencia cruzada: presupuestos.cliente_id -> clientes(id).
-- clientes vive en 02_procurador_master.sql: aplicar ese script
-- antes que este en un despliegue desde cero.
--
-- Idempotente: seguro de re-ejecutar contra una base ya poblada.
-- ============================================================

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ------------------------------------------------------------
-- Ledger genérico de registros inmutables (usado por line_items
-- y por audit_chain para el hash-chain de integridad)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS records (
    record_id       uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    content_hash    text NOT NULL,
    raw_payload     jsonb NOT NULL,
    idempotency_key text NOT NULL,
    created_at      timestamptz DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS records_idempotency_key_key ON records(idempotency_key);

CREATE TABLE IF NOT EXISTS audit_chain (
    event_id   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    record_id  uuid REFERENCES records(record_id),
    event_type text NOT NULL,
    event_hash text NOT NULL,
    created_at timestamptz DEFAULT now()
);
ALTER TABLE audit_chain ENABLE ROW LEVEL SECURITY;

CREATE TABLE IF NOT EXISTS user_keys (
    user_id    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    public_key text NOT NULL,
    algorithm  text NOT NULL DEFAULT 'RSA',
    created_at timestamptz DEFAULT now()
);
ALTER TABLE user_keys ENABLE ROW LEVEL SECURITY;

CREATE OR REPLACE FUNCTION enforce_chain_hash()
RETURNS trigger
LANGUAGE plpgsql
AS $function$
begin
  new.event_hash := encode(digest(new.record_id::text || new.event_type, 'sha256'), 'hex');
  return new;
end;
$function$;

DROP TRIGGER IF EXISTS trg_hash ON audit_chain;
CREATE TRIGGER trg_hash BEFORE INSERT ON audit_chain
    FOR EACH ROW EXECUTE FUNCTION enforce_chain_hash();

-- ------------------------------------------------------------
-- Decretos SERVIU y su contenido normativo
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS decretos (
    id                 SERIAL PRIMARY KEY,
    numero             varchar(20) NOT NULL UNIQUE,
    titulo             text,
    fecha_publicacion  date,
    url                text,
    created_at         timestamptz DEFAULT now()
);
COMMENT ON COLUMN decretos.numero IS 'Número del decreto (ej: 49)';
CREATE INDEX IF NOT EXISTS idx_decretos_numero ON decretos(numero);
ALTER TABLE decretos ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "bi_readonly_decretos" ON decretos;
CREATE POLICY "bi_readonly_decretos" ON decretos FOR SELECT TO bi_readonly USING (true);

CREATE TABLE IF NOT EXISTS decreto_articulos (
    id         SERIAL PRIMARY KEY,
    decreto_id integer NOT NULL REFERENCES decretos(id) ON DELETE CASCADE,
    numero     varchar(20),
    contenido  text,
    created_at timestamptz DEFAULT now()
);
COMMENT ON COLUMN decreto_articulos.decreto_id IS 'Referencia al decreto padre';
CREATE INDEX IF NOT EXISTS idx_decreto_articulos_decreto ON decreto_articulos(decreto_id);
ALTER TABLE decreto_articulos ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "bi_readonly_decreto_articulos" ON decreto_articulos;
CREATE POLICY "bi_readonly_decreto_articulos" ON decreto_articulos FOR SELECT TO bi_readonly USING (true);

CREATE TABLE IF NOT EXISTS decreto_materiales (
    id              SERIAL PRIMARY KEY,
    decreto_id      integer NOT NULL REFERENCES decretos(id) ON DELETE CASCADE,
    nombre_material text NOT NULL,
    codigo_unidad   varchar(20),
    descripcion     text,
    line_item_id    integer,
    created_at      timestamptz DEFAULT now()
);
COMMENT ON COLUMN decreto_materiales.line_item_id IS 'ID de line_items (referencia manual, sin FK)';
CREATE INDEX IF NOT EXISTS idx_decreto_materiales_decreto ON decreto_materiales(decreto_id);
CREATE INDEX IF NOT EXISTS idx_decreto_materiales_nombre ON decreto_materiales(nombre_material);
ALTER TABLE decreto_materiales ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "bi_readonly_decreto_materiales" ON decreto_materiales;
CREATE POLICY "bi_readonly_decreto_materiales" ON decreto_materiales FOR SELECT TO bi_readonly USING (true);

CREATE TABLE IF NOT EXISTS line_items (
    line_item_id    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    record_id       uuid REFERENCES records(record_id) ON DELETE CASCADE,
    cantidad        numeric NOT NULL,
    material        text NOT NULL,
    precio_unitario numeric NOT NULL,
    rubro           text,
    created_at      timestamptz DEFAULT now()
);
ALTER TABLE line_items ENABLE ROW LEVEL SECURITY;

-- ------------------------------------------------------------
-- Precios SERVIU y reglas de clasificación por rubro
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS precios_serviu (
    id              SERIAL PRIMARY KEY,
    item            text NOT NULL,
    unidad          text,
    valor_unitario  numeric NOT NULL,
    fuente          text,
    idempotency_key text NOT NULL UNIQUE,
    created_at      timestamptz DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_precios_serviu_item ON precios_serviu(item);
ALTER TABLE precios_serviu ENABLE ROW LEVEL SECURITY;

CREATE TABLE IF NOT EXISTS reglas_rubros (
    id            SERIAL PRIMARY KEY,
    palabra_clave text NOT NULL,
    rubro         text NOT NULL,
    prioridad     integer NOT NULL DEFAULT 0,
    created_at    timestamptz DEFAULT now(),
    UNIQUE (palabra_clave, rubro)
);
CREATE INDEX IF NOT EXISTS idx_reglas_rubros_prioridad ON reglas_rubros(prioridad DESC);

CREATE TABLE IF NOT EXISTS reglas_rubros_exclusiones (
    id               SERIAL PRIMARY KEY,
    rubro            text NOT NULL,
    palabra_excluida text NOT NULL,
    created_at       timestamptz DEFAULT now(),
    UNIQUE (rubro, palabra_excluida)
);

CREATE TABLE IF NOT EXISTS reglas_contables (
    id                       bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    rubro_nombre             text NOT NULL,
    cuenta_contable_sugerida text NOT NULL,
    palabras_clave_json      jsonb NOT NULL DEFAULT '[]'::jsonb,
    prioridad                integer NOT NULL DEFAULT 0,
    created_at               timestamptz NOT NULL DEFAULT now(),
    updated_at               timestamptz
);
ALTER TABLE reglas_contables ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "anon_auth_select_reglas" ON reglas_contables;
CREATE POLICY "anon_auth_select_reglas" ON reglas_contables FOR SELECT TO anon, authenticated USING (true);
DROP POLICY IF EXISTS "auth_insert_reglas" ON reglas_contables;
CREATE POLICY "auth_insert_reglas" ON reglas_contables FOR INSERT TO authenticated WITH CHECK (true);

CREATE TABLE IF NOT EXISTS auditoria_movimientos (
    movimiento_id    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    monto            numeric(12,2) NOT NULL,
    descripcion      text NOT NULL,
    clasificacion_ia text,
    confianza_ia     numeric(3,2),
    estado_revision  text NOT NULL DEFAULT 'PENDIENTE_REVISION'
        CHECK (estado_revision IN ('CLASIFICADO', 'PENDIENTE_REVISION', 'RECHAZADO', 'CONFIRMADO')),
    regla_usada_id   bigint REFERENCES reglas_contables(id),
    fecha_movimiento date,
    raw_csv_line     text,
    created_at       timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE auditoria_movimientos ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "anon_auth_select_auditoria" ON auditoria_movimientos;
CREATE POLICY "anon_auth_select_auditoria" ON auditoria_movimientos FOR SELECT TO anon, authenticated USING (true);
DROP POLICY IF EXISTS "auth_insert_auditoria" ON auditoria_movimientos;
CREATE POLICY "auth_insert_auditoria" ON auditoria_movimientos FOR INSERT TO authenticated WITH CHECK (true);

-- ------------------------------------------------------------
-- Presupuestos históricos (fuente de entrenamiento ML, ver
-- memoria de proyecto: Opción A sobre scraping)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS presupuestos (
    id                 SERIAL PRIMARY KEY,
    cliente            text,
    tarea              text,
    maestro            text,
    fecha              date,
    total              double precision,
    m2                 double precision,
    estado             text,
    descripcion        text,
    incluye_materiales boolean DEFAULT false,
    created_at         timestamptz DEFAULT now(),
    cliente_id         uuid REFERENCES clientes(id),
    nombre             text,
    monto_total        numeric(14,2) DEFAULT 0,
    codigo             text UNIQUE,
    updated_at         timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_pres_estado ON presupuestos(estado);
CREATE INDEX IF NOT EXISTS idx_pres_tarea ON presupuestos(tarea);
ALTER TABLE presupuestos ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Permitir_Lectura_Total" ON presupuestos;
CREATE POLICY "Permitir_Lectura_Total" ON presupuestos FOR SELECT USING (true);
DROP POLICY IF EXISTS "Permitir_Update_Total" ON presupuestos;
CREATE POLICY "Permitir_Update_Total" ON presupuestos FOR UPDATE USING (true) WITH CHECK (true);
DROP POLICY IF EXISTS "bi_readonly_access" ON presupuestos;
CREATE POLICY "bi_readonly_access" ON presupuestos FOR SELECT TO bi_readonly USING (true);

CREATE TABLE IF NOT EXISTS partidas_presupuesto (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    presupuesto_id  integer NOT NULL REFERENCES presupuestos(id) ON DELETE CASCADE,
    descripcion     text NOT NULL,
    cantidad        numeric(10,2) NOT NULL DEFAULT 1,
    precio_unitario numeric(14,2) NOT NULL DEFAULT 0,
    orden           integer DEFAULT 0
);
