-- ============================================================
-- 06_agentes_marketing_ddl.sql
-- Proyecto: DepaFix / Agencia Ikki (CEO de Marketing)
-- Fase 1 - Día 1: Infraestructura de datos
--
-- Objetivo:
--   Definir las tablas de telemetría del Agente Ikki en Supabase:
--   1) campanas_ikki: campañas, estructura CDA, presupuesto y fee.
--   2) leads_ikki:    captación y seguimiento de prospectos.
--
-- Notas:
--   - Script local. No ejecutar aún contra la nube.
--   - RLS y políticas de acceso se configuran en el Día 3.
--   - IDs UUID, timestamps con zona horaria y JSONB para metadatos.
-- ============================================================


-- ============================================================
-- TABLA 1: campanas_ikki
-- Registra la simulación/ejecución de una campaña y su economía.
-- ============================================================

CREATE TABLE IF NOT EXISTS public.campanas_ikki (
    id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cliente_id               TEXT NOT NULL,
    nombre                   TEXT NOT NULL,
    rubro                    TEXT,
    plataforma               TEXT NOT NULL DEFAULT 'Meta',
    estado                   TEXT NOT NULL DEFAULT 'simulada',

    -- Estructura CDA: contexto, diagnóstico y acción de la campaña.
    estructura_cda           JSONB NOT NULL DEFAULT '{}'::jsonb,

    -- Economía de la campaña (CLP).
    presupuesto_pauta_clp    NUMERIC(14,2) NOT NULL DEFAULT 0,
    fee_fijo_clp             NUMERIC(14,2) NOT NULL DEFAULT 0,
    pct_pauta                NUMERIC(5,4)  NOT NULL DEFAULT 0.1500,
    comision_agencia_clp     NUMERIC(14,2) NOT NULL DEFAULT 0,
    total_facturar_clp       NUMERIC(14,2) NOT NULL DEFAULT 0,
    margen_agencia_clp       NUMERIC(14,2) NOT NULL DEFAULT 0,

    -- Resultados de la simulación / plan de medios.
    proyecciones             JSONB NOT NULL DEFAULT '{}'::jsonb,
    benchmarks               JSONB NOT NULL DEFAULT '{}'::jsonb,
    plan_vuelo               JSONB NOT NULL DEFAULT '[]'::jsonb,
    copys                    JSONB NOT NULL DEFAULT '[]'::jsonb,
    metadatos                JSONB NOT NULL DEFAULT '{}'::jsonb,

    -- Vigencia.
    fecha_inicio             DATE NOT NULL DEFAULT CURRENT_DATE,
    fecha_fin                DATE,

    -- Auditoría.
    created_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at               TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT campanas_ikki_plataforma_check
        CHECK (plataforma IN ('Meta', 'Google', 'TikTok', 'Otra')),
    CONSTRAINT campanas_ikki_estado_check
        CHECK (estado IN ('simulada', 'activa', 'pausada', 'finalizada', 'cancelada')),
    CONSTRAINT campanas_ikki_cda_check
        CHECK (jsonb_typeof(estructura_cda) = 'object'),
    CONSTRAINT campanas_ikki_presupuesto_check
        CHECK (presupuesto_pauta_clp >= 0),
    CONSTRAINT campanas_ikki_fee_fijo_check
        CHECK (fee_fijo_clp >= 0),
    CONSTRAINT campanas_ikki_pct_pauta_check
        CHECK (pct_pauta >= 0 AND pct_pauta <= 1),
    CONSTRAINT campanas_ikki_comision_check
        CHECK (comision_agencia_clp >= 0),
    CONSTRAINT campanas_ikki_total_facturar_check
        CHECK (total_facturar_clp >= 0),
    CONSTRAINT campanas_ikki_margen_check
        CHECK (margen_agencia_clp >= 0),
    CONSTRAINT campanas_ikki_proyecciones_check
        CHECK (jsonb_typeof(proyecciones) = 'object'),
    CONSTRAINT campanas_ikki_benchmarks_check
        CHECK (jsonb_typeof(benchmarks) = 'object'),
    CONSTRAINT campanas_ikki_plan_vuelo_check
        CHECK (jsonb_typeof(plan_vuelo) = 'array'),
    CONSTRAINT campanas_ikki_copys_check
        CHECK (jsonb_typeof(copys) = 'array'),
    CONSTRAINT campanas_ikki_metadatos_check
        CHECK (jsonb_typeof(metadatos) = 'object'),
    CONSTRAINT campanas_ikki_fechas_check
        CHECK (fecha_fin IS NULL OR fecha_fin >= fecha_inicio)
);

COMMENT ON TABLE public.campanas_ikki IS
    'Campañas simuladas/activas del Agente Ikki con estructura CDA y economía de agencia.';
COMMENT ON COLUMN public.campanas_ikki.cliente_id IS
    'Identificador externo del cliente/prospecto (CRM, Telegram o ID de negocio).';
COMMENT ON COLUMN public.campanas_ikki.estructura_cda IS
    'Estructura CDA en JSONB. Claves sugeridas: contexto, diagnostico, accion, oferta, publico.';
COMMENT ON COLUMN public.campanas_ikki.presupuesto_pauta_clp IS
    'Inversión neta destinada a Meta/Google Ads, en pesos chilenos.';
COMMENT ON COLUMN public.campanas_ikki.pct_pauta IS
    'Comisión de agencia sobre la pauta (0.1500 = 15%).';
COMMENT ON COLUMN public.campanas_ikki.total_facturar_clp IS
    'Fee fijo + pauta + comisión de agencia.';
COMMENT ON COLUMN public.campanas_ikki.margen_agencia_clp IS
    'Ingreso de la agencia: fee fijo + comisión sobre pauta.';


-- ============================================================
-- TABLA 2: leads_ikki
-- Captación y seguimiento comercial de prospectos.
-- ============================================================

CREATE TABLE IF NOT EXISTS public.leads_ikki (
    id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    campana_id               UUID REFERENCES public.campanas_ikki(id) ON DELETE SET NULL,
    idempotency_key          TEXT UNIQUE,

    -- Datos de contacto.
    nombre                   TEXT NOT NULL,
    email                    TEXT,
    telefono                 TEXT,
    empresa                  TEXT,
    rubro                    TEXT,

    -- Atribución y estado comercial.
    fuente                   TEXT NOT NULL DEFAULT 'desconocida',
    estado                   TEXT NOT NULL DEFAULT 'nuevo',
    score                    SMALLINT NOT NULL DEFAULT 0,
    valor_estimado_clp       NUMERIC(14,2) NOT NULL DEFAULT 0,

    -- Datos de campaña y consentimiento.
    utm                      JSONB NOT NULL DEFAULT '{}'::jsonb,
    metadatos                JSONB NOT NULL DEFAULT '{}'::jsonb,
    consentimiento_marketing BOOLEAN NOT NULL DEFAULT FALSE,
    fecha_consentimiento     TIMESTAMPTZ,

    -- Auditoría.
    created_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at               TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT leads_ikki_estado_check
        CHECK (estado IN ('nuevo', 'contactado', 'calificado', 'propuesta', 'ganado', 'perdido')),
    CONSTRAINT leads_ikki_score_check
        CHECK (score >= 0 AND score <= 100),
    CONSTRAINT leads_ikki_valor_check
        CHECK (valor_estimado_clp >= 0),
    CONSTRAINT leads_ikki_utm_check
        CHECK (jsonb_typeof(utm) = 'object'),
    CONSTRAINT leads_ikki_metadatos_check
        CHECK (jsonb_typeof(metadatos) = 'object')
);

COMMENT ON TABLE public.leads_ikki IS
    'Leads captados por las campañas del Agente Ikki y su estado comercial.';
COMMENT ON COLUMN public.leads_ikki.campana_id IS
    'Campaña de origen. Se conserva el lead si la campaña se elimina.';
COMMENT ON COLUMN public.leads_ikki.idempotency_key IS
    'Clave única para evitar duplicados en ingestas desde Meta/Google/Webhooks.';
COMMENT ON COLUMN public.leads_ikki.fuente IS
    'Origen del lead: meta, google, tiktok, organico, referido, etc.';
COMMENT ON COLUMN public.leads_ikki.score IS
    'Prioridad comercial del lead (0 a 100).';
COMMENT ON COLUMN public.leads_ikki.utm IS
    'Parámetros UTM y datos de atribución en JSONB.';


-- ============================================================
-- ÍNDICES
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_campanas_ikki_cliente
    ON public.campanas_ikki (cliente_id);

CREATE INDEX IF NOT EXISTS idx_campanas_ikki_estado
    ON public.campanas_ikki (estado);

CREATE INDEX IF NOT EXISTS idx_campanas_ikki_fecha_inicio
    ON public.campanas_ikki (fecha_inicio DESC);

CREATE INDEX IF NOT EXISTS idx_campanas_ikki_cda_gin
    ON public.campanas_ikki USING GIN (estructura_cda);

CREATE INDEX IF NOT EXISTS idx_campanas_ikki_metadatos_gin
    ON public.campanas_ikki USING GIN (metadatos);

CREATE INDEX IF NOT EXISTS idx_leads_ikki_campana
    ON public.leads_ikki (campana_id);

CREATE INDEX IF NOT EXISTS idx_leads_ikki_estado
    ON public.leads_ikki (estado);

CREATE INDEX IF NOT EXISTS idx_leads_ikki_created_at
    ON public.leads_ikki (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_leads_ikki_email
    ON public.leads_ikki (lower(email))
    WHERE email IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_leads_ikki_metadatos_gin
    ON public.leads_ikki USING GIN (metadatos);


-- ============================================================
-- ACTUALIZACIÓN AUTOMÁTICA DE updated_at
-- ============================================================

CREATE OR REPLACE FUNCTION public.ikki_set_updated_at()
RETURNS TRIGGER
LANGUAGE plpgsql
SET search_path = public
AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_campanas_ikki_updated_at ON public.campanas_ikki;
CREATE TRIGGER trg_campanas_ikki_updated_at
    BEFORE UPDATE ON public.campanas_ikki
    FOR EACH ROW
    EXECUTE FUNCTION public.ikki_set_updated_at();

DROP TRIGGER IF EXISTS trg_leads_ikki_updated_at ON public.leads_ikki;
CREATE TRIGGER trg_leads_ikki_updated_at
    BEFORE UPDATE ON public.leads_ikki
    FOR EACH ROW
    EXECUTE FUNCTION public.ikki_set_updated_at();


-- ============================================================
-- FIN DEL DÍA 1
-- Pendiente Día 3: habilitar RLS y crear políticas por rol.
-- ============================================================
