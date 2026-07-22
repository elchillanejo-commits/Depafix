-- ============================================================
-- 02_procurador_master.sql
-- Dominio PROCURADOR: clientes, tokens/compras/consultas,
-- catálogo de ítems con sinónimos legales, estudios jurídicos
-- y bitácoras de compliance/errores.
-- Generado a partir del esquema real de Supabase.
--
-- Aplicar ANTES que 01_serviu_master.sql en un despliegue desde
-- cero: presupuestos.cliente_id referencia clientes(id).
--
-- Idempotente: seguro de re-ejecutar contra una base ya poblada.
-- ============================================================

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS clientes (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    nombre         text NOT NULL,
    rut            text,
    rubro          text,
    fecha_creacion timestamptz NOT NULL DEFAULT now(),
    estado         text NOT NULL DEFAULT 'activo' CHECK (estado IN ('activo', 'inactivo')),
    telefono       text,
    direccion      text,
    comuna         text
);
CREATE INDEX IF NOT EXISTS idx_clientes_estado ON clientes(estado);
CREATE UNIQUE INDEX IF NOT EXISTS idx_clientes_rut ON clientes(rut) WHERE rut IS NOT NULL;

CREATE TABLE IF NOT EXISTS tokens (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    usuario_id          uuid NOT NULL REFERENCES clientes(id) ON DELETE CASCADE,
    codigo_token        text NOT NULL UNIQUE,
    consultas_restantes integer NOT NULL DEFAULT 0 CHECK (consultas_restantes >= 0),
    fecha_compra        timestamptz NOT NULL,
    fecha_expiracion    timestamptz,
    CONSTRAINT chk_expiracion_posterior CHECK (
        fecha_expiracion IS NULL OR fecha_compra IS NULL OR fecha_expiracion > fecha_compra
    )
);
CREATE INDEX IF NOT EXISTS idx_tokens_usuario_id ON tokens(usuario_id);

CREATE TABLE IF NOT EXISTS compras (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    cliente_id   uuid NOT NULL REFERENCES clientes(id) ON DELETE CASCADE,
    token_id     uuid REFERENCES tokens(id) ON DELETE SET NULL,
    cantidad     integer NOT NULL CHECK (cantidad > 0),
    monto        numeric,
    metodo_pago  text NOT NULL DEFAULT 'mock',
    fecha_compra timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_compras_cliente_id ON compras(cliente_id);
CREATE INDEX IF NOT EXISTS idx_compras_token_id ON compras(token_id);

CREATE TABLE IF NOT EXISTS consultas (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    cliente_id     uuid NOT NULL REFERENCES clientes(id) ON DELETE CASCADE,
    tipo_consulta  text NOT NULL,
    detalle        jsonb,
    fecha_consulta timestamptz NOT NULL DEFAULT now(),
    token_usado    integer NOT NULL DEFAULT 0 CHECK (token_usado >= 0)
);
CREATE INDEX IF NOT EXISTS idx_consultas_cliente_id ON consultas(cliente_id);
CREATE INDEX IF NOT EXISTS idx_consultas_fecha ON consultas(fecha_consulta DESC);
CREATE INDEX IF NOT EXISTS idx_consultas_tipo ON consultas(tipo_consulta);

-- Catálogo de ítems con sinónimos, usado por el matcher legal
-- (endpoint /api/procurador/consultar)
CREATE TABLE IF NOT EXISTS items_catalogo (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    nombre             text NOT NULL,
    nombre_normalizado text NOT NULL UNIQUE,
    categoria          text,
    precio_interno     numeric(14,2),
    precio_cliente     numeric(14,2),
    created_at         timestamptz NOT NULL DEFAULT now(),
    updated_at         timestamptz NOT NULL DEFAULT now(),
    sinonimos          text[] DEFAULT '{}',
    observaciones      text
);

CREATE TABLE IF NOT EXISTS law_firms (
    firm_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name    text NOT NULL
);

CREATE TABLE IF NOT EXISTS usuarios (
    id       SERIAL PRIMARY KEY,
    auth_id  uuid UNIQUE,
    nombre   text,
    email    text UNIQUE,
    password text
);

CREATE TABLE IF NOT EXISTS compliance_logs (
    id               SERIAL PRIMARY KEY,
    rol              varchar(50),
    etapa_procesal   varchar(100),
    riesgo_detectado text,
    dictamen         varchar(50),
    metadata         jsonb DEFAULT '{}',
    created_at       timestamp DEFAULT now()
);
COMMENT ON TABLE compliance_logs IS 'Registros de análisis de compliance para el Procurador Virtual';
COMMENT ON COLUMN compliance_logs.rol IS 'ROL del expediente legal';
COMMENT ON COLUMN compliance_logs.etapa_procesal IS 'Etapa del proceso legal';
COMMENT ON COLUMN compliance_logs.riesgo_detectado IS 'Descripción del riesgo detectado';
COMMENT ON COLUMN compliance_logs.dictamen IS 'Dictamen del análisis (APROBADO, RECHAZADO, NEGOCIAR, PENDIENTE)';
COMMENT ON COLUMN compliance_logs.metadata IS 'Metadatos adicionales (tribunal, litigantes, etc.)';
CREATE INDEX IF NOT EXISTS idx_compliance_logs_rol ON compliance_logs(rol);
CREATE INDEX IF NOT EXISTS idx_compliance_logs_created ON compliance_logs(created_at);
ALTER TABLE compliance_logs ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "bi_readonly_compliance_logs" ON compliance_logs;
CREATE POLICY "bi_readonly_compliance_logs" ON compliance_logs FOR SELECT TO bi_readonly USING (true);

CREATE TABLE IF NOT EXISTS error_logs (
    id           SERIAL PRIMARY KEY,
    modulo       varchar(50),
    funcion      varchar(100),
    mensaje      text,
    stack_trace  text,
    metadata     jsonb DEFAULT '{}',
    created_at   timestamp DEFAULT now()
);
COMMENT ON TABLE error_logs IS 'Bitácora de errores de todos los agentes';
COMMENT ON COLUMN error_logs.modulo IS 'Módulo donde ocurrió el error';
COMMENT ON COLUMN error_logs.funcion IS 'Función que falló';
COMMENT ON COLUMN error_logs.mensaje IS 'Mensaje de error';
COMMENT ON COLUMN error_logs.stack_trace IS 'Traza completa del error';
COMMENT ON COLUMN error_logs.metadata IS 'Metadatos adicionales del contexto';
CREATE INDEX IF NOT EXISTS idx_error_logs_modulo ON error_logs(modulo);
CREATE INDEX IF NOT EXISTS idx_error_logs_created ON error_logs(created_at);
ALTER TABLE error_logs ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "bi_readonly_error_logs" ON error_logs;
CREATE POLICY "bi_readonly_error_logs" ON error_logs FOR SELECT TO bi_readonly USING (true);

-- Casos de compliance pendientes de los últimos 30 días (antes
-- sql/04_VISTAS_GESTION.sql).
CREATE OR REPLACE VIEW active_compliance_tasks AS
SELECT id, rol, etapa_procesal, riesgo_detectado, created_at, dictamen
FROM compliance_logs
WHERE (dictamen = 'Negociar' OR dictamen IS NULL)
  AND created_at > (NOW() - INTERVAL '30 days');
COMMENT ON VIEW active_compliance_tasks IS 'Casos pendientes últimos 30 días';
