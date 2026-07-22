-- ============================================================
-- 06_agentes_master.sql
-- Dominio AGENTES: salud/heartbeat de agentes, campañas de
-- marketing (Meta), métricas diarias, leads y base de
-- conocimiento. Generado a partir del esquema real de Supabase.
--
-- Idempotente: seguro de re-ejecutar contra una base ya poblada.
-- ============================================================

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS salud_agentes (
    id           bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    agente       text NOT NULL,
    estado       text NOT NULL CHECK (estado IN ('online', 'offline', 'error', 'warning')),
    ultimo_ciclo timestamptz,
    mensaje      text,
    metricas     jsonb,
    created_at   timestamptz DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_salud_agente_created ON salud_agentes(agente, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_salud_estado ON salud_agentes(estado);
CREATE INDEX IF NOT EXISTS idx_salud_ultimo_ciclo ON salud_agentes(ultimo_ciclo);
ALTER TABLE salud_agentes ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "salud_agentes_insert_policy" ON salud_agentes;
CREATE POLICY "salud_agentes_insert_policy" ON salud_agentes FOR INSERT WITH CHECK (true);
DROP POLICY IF EXISTS "salud_agentes_select_policy" ON salud_agentes;
CREATE POLICY "salud_agentes_select_policy" ON salud_agentes FOR SELECT USING (true);

CREATE TABLE IF NOT EXISTS sys_status (
    agent_name     text PRIMARY KEY,
    last_heartbeat timestamptz DEFAULT now(),
    status         text NOT NULL,
    last_error     text
);

CREATE TABLE IF NOT EXISTS campanas (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tipo       text NOT NULL,
    titulo     text NOT NULL,
    url_afiche text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS campanas_meta (
    id                  SERIAL PRIMARY KEY,
    cliente_id          varchar(50),
    nombre              varchar(255),
    objetivo            varchar(50),
    presupuesto_diario  numeric(10,2),
    presupuesto_total   numeric(10,2),
    fecha_inicio        date,
    fecha_fin           date,
    estado              varchar(20),
    meta_campania_id    varchar(50),
    configuracion       jsonb,
    created_at          timestamp DEFAULT now()
);
COMMENT ON COLUMN campanas_meta.objetivo IS 'Objetivo de la campaña: CONVERSIONS, TRAFFIC, REACH, etc.';
COMMENT ON COLUMN campanas_meta.estado IS 'Estado de la campaña: ACTIVE, PAUSED, COMPLETED';
CREATE INDEX IF NOT EXISTS idx_campanas_cliente ON campanas_meta(cliente_id);
CREATE INDEX IF NOT EXISTS idx_campanas_estado ON campanas_meta(estado);
ALTER TABLE campanas_meta ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Solo service_role puede insertar campanas" ON campanas_meta;
CREATE POLICY "Solo service_role puede insertar campanas" ON campanas_meta FOR INSERT WITH CHECK (true);
DROP POLICY IF EXISTS "Todos pueden leer campanas" ON campanas_meta;
CREATE POLICY "Todos pueden leer campanas" ON campanas_meta FOR SELECT USING (true);

CREATE TABLE IF NOT EXISTS metricas_diarias (
    id           SERIAL PRIMARY KEY,
    campania_id  integer REFERENCES campanas_meta(id) ON DELETE CASCADE,
    fecha        date,
    impresiones  integer,
    clicks       integer,
    conversiones integer,
    costo        numeric(10,2),
    ctr          numeric(5,2),
    cpa          numeric(10,2),
    roi          numeric(5,2),
    metadata     jsonb,
    created_at   timestamp DEFAULT now()
);
COMMENT ON COLUMN metricas_diarias.campania_id IS 'Referencia a la campaña en campanas_meta';
CREATE INDEX IF NOT EXISTS idx_metricas_campania ON metricas_diarias(campania_id);
CREATE INDEX IF NOT EXISTS idx_metricas_fecha ON metricas_diarias(fecha);
ALTER TABLE metricas_diarias ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Solo service_role puede insertar metricas" ON metricas_diarias;
CREATE POLICY "Solo service_role puede insertar metricas" ON metricas_diarias FOR INSERT WITH CHECK (true);
DROP POLICY IF EXISTS "Todos pueden leer metricas" ON metricas_diarias;
CREATE POLICY "Todos pueden leer metricas" ON metricas_diarias FOR SELECT USING (true);

CREATE TABLE IF NOT EXISTS leads (
    id         SERIAL PRIMARY KEY,
    nombre     varchar(255),
    email      varchar(255),
    telefono   varchar(50),
    empresa    varchar(255),
    rubro      varchar(100),
    fuente     varchar(50),
    score      integer DEFAULT 0,
    estado     varchar(20) DEFAULT 'PENDIENTE',
    metadata   jsonb,
    created_at timestamp DEFAULT now()
);
COMMENT ON COLUMN leads.fuente IS 'Fuente del lead: instagram, facebook, web, referral';
COMMENT ON COLUMN leads.estado IS 'Estado: PENDIENTE, CONTACTADO, CONVERTIDO, PERDIDO';
CREATE INDEX IF NOT EXISTS idx_leads_estado ON leads(estado);
CREATE INDEX IF NOT EXISTS idx_leads_fuente ON leads(fuente);
ALTER TABLE leads ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Solo service_role puede insertar leads" ON leads;
CREATE POLICY "Solo service_role puede insertar leads" ON leads FOR INSERT WITH CHECK (true);
DROP POLICY IF EXISTS "Todos pueden leer leads" ON leads;
CREATE POLICY "Todos pueden leer leads" ON leads FOR SELECT USING (true);

CREATE TABLE IF NOT EXISTS knowledge_entries (
    id                SERIAL PRIMARY KEY,
    fuente            varchar(50) NOT NULL,
    url               text,
    titulo            varchar(500),
    contenido         text,
    resumen           text,
    palabras_clave    text[],
    fecha_extraccion  timestamp DEFAULT now(),
    metadata          jsonb DEFAULT '{}'
);
COMMENT ON COLUMN knowledge_entries.fuente IS 'Fuente del conocimiento: youtube, twitter, instagram, facebook, rss, web';
COMMENT ON COLUMN knowledge_entries.palabras_clave IS 'Array de palabras clave extraídas del contenido';
COMMENT ON COLUMN knowledge_entries.metadata IS 'Metadatos adicionales (ej: autor, fecha_publicacion, views, etc.)';
CREATE INDEX IF NOT EXISTS idx_knowledge_fecha ON knowledge_entries(fecha_extraccion DESC);
CREATE INDEX IF NOT EXISTS idx_knowledge_fuente ON knowledge_entries(fuente);
CREATE INDEX IF NOT EXISTS idx_knowledge_palabras_clave ON knowledge_entries USING gin(palabras_clave);
ALTER TABLE knowledge_entries ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Usuarios autenticados pueden leer" ON knowledge_entries;
CREATE POLICY "Usuarios autenticados pueden leer" ON knowledge_entries FOR SELECT USING (true);
