-- ============================================================
-- 07_ikki_telemetria_gestalt.sql
-- Proyecto: DepaFix / Agencia Ikki
-- Cliente: Gestalt Medical (diagnóstico genético y optimización clínica)
--
-- Objetivo:
--   1) Extender campanas_ikki con embudo B2C/B2B y presupuesto mensual.
--   2) Extender leads_ikki con procedencia especializada y UTM.
--   3) Crear presupuestos_ikki y la vista de presupuesto mensual.
--
-- Requiere haber ejecutado primero:
--   public.campanas_ikki y public.leads_ikki (06_agentes_marketing_ddl.sql)
--
-- RLS se configura en el Día 3. Este script no toca políticas.
-- ============================================================

DO $$
BEGIN
    IF to_regclass('public.campanas_ikki') IS NULL
       OR to_regclass('public.leads_ikki') IS NULL THEN
        RAISE EXCEPTION
            'Faltan tablas base. Ejecuta 06_agentes_marketing_ddl.sql antes de este archivo.';
    END IF;
END;
$$;


-- ============================================================
-- 1. CAMPANAS: separación de embudos y periodo mensual
-- ============================================================

ALTER TABLE public.campanas_ikki
    ADD COLUMN IF NOT EXISTS grupo_simulacion_id UUID NOT NULL DEFAULT gen_random_uuid(),
    ADD COLUMN IF NOT EXISTS embudo TEXT NOT NULL DEFAULT 'B2C',
    ADD COLUMN IF NOT EXISTS objetivo TEXT,
    ADD COLUMN IF NOT EXISTS publico_objetivo TEXT,
    ADD COLUMN IF NOT EXISTS canal_principal TEXT,
    ADD COLUMN IF NOT EXISTS canales_secundarios JSONB NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS periodo_mes DATE,
    ADD COLUMN IF NOT EXISTS kpis_objetivo JSONB NOT NULL DEFAULT '{}'::jsonb;

UPDATE public.campanas_ikki
SET periodo_mes = date_trunc('month', fecha_inicio)::date
WHERE periodo_mes IS NULL;

ALTER TABLE public.campanas_ikki
    DROP CONSTRAINT IF EXISTS campanas_ikki_embudo_check;
ALTER TABLE public.campanas_ikki
    ADD CONSTRAINT campanas_ikki_embudo_check
    CHECK (embudo IN ('B2C', 'B2B'));

ALTER TABLE public.campanas_ikki
    DROP CONSTRAINT IF EXISTS campanas_ikki_periodo_mes_check;
ALTER TABLE public.campanas_ikki
    ADD CONSTRAINT campanas_ikki_periodo_mes_check
    CHECK (periodo_mes IS NULL OR periodo_mes = date_trunc('month', periodo_mes)::date);

ALTER TABLE public.campanas_ikki
    DROP CONSTRAINT IF EXISTS campanas_ikki_canales_secundarios_check;
ALTER TABLE public.campanas_ikki
    ADD CONSTRAINT campanas_ikki_canales_secundarios_check
    CHECK (jsonb_typeof(canales_secundarios) = 'array');

ALTER TABLE public.campanas_ikki
    DROP CONSTRAINT IF EXISTS campanas_ikki_kpis_objetivo_check;
ALTER TABLE public.campanas_ikki
    ADD CONSTRAINT campanas_ikki_kpis_objetivo_check
    CHECK (jsonb_typeof(kpis_objetivo) = 'object');

ALTER TABLE public.campanas_ikki
    DROP CONSTRAINT IF EXISTS campanas_ikki_grupo_embudo_key;
ALTER TABLE public.campanas_ikki
    ADD CONSTRAINT campanas_ikki_grupo_embudo_key
    UNIQUE (grupo_simulacion_id, embudo);

CREATE INDEX IF NOT EXISTS idx_campanas_ikki_cliente_periodo_embudo
    ON public.campanas_ikki (cliente_id, periodo_mes, embudo);

CREATE INDEX IF NOT EXISTS idx_campanas_ikki_grupo_simulacion
    ON public.campanas_ikki (grupo_simulacion_id);

COMMENT ON COLUMN public.campanas_ikki.presupuesto_pauta_clp IS
    'Presupuesto mensual de pauta asignado a esta campaña/embudo, en CLP.';
COMMENT ON COLUMN public.campanas_ikki.grupo_simulacion_id IS
    'Agrupa las campañas B2C y B2B generadas por una misma simulación.';
COMMENT ON COLUMN public.campanas_ikki.embudo IS
    'Embudo comercial: B2C (pacientes/familias) o B2B (clínicas/laboratorios).';
COMMENT ON COLUMN public.campanas_ikki.periodo_mes IS
    'Primer día del mes presupuestado.';


-- ============================================================
-- 2. LEADS: procedencia especializada y atribución
-- ============================================================

ALTER TABLE public.leads_ikki
    ADD COLUMN IF NOT EXISTS cliente_id TEXT NOT NULL DEFAULT 'sin_asignar',
    ADD COLUMN IF NOT EXISTS embudo TEXT NOT NULL DEFAULT 'B2C',
    ADD COLUMN IF NOT EXISTS tipo_lead TEXT,
    ADD COLUMN IF NOT EXISTS origen_plataforma TEXT,
    ADD COLUMN IF NOT EXISTS origen_campana TEXT,
    ADD COLUMN IF NOT EXISTS origen_anuncio TEXT,
    ADD COLUMN IF NOT EXISTS origen_conjunto TEXT,
    ADD COLUMN IF NOT EXISTS utm_source TEXT,
    ADD COLUMN IF NOT EXISTS utm_medium TEXT,
    ADD COLUMN IF NOT EXISTS utm_campaign TEXT,
    ADD COLUMN IF NOT EXISTS utm_content TEXT,
    ADD COLUMN IF NOT EXISTS utm_term TEXT,
    ADD COLUMN IF NOT EXISTS pagina_aterrizaje TEXT,
    ADD COLUMN IF NOT EXISTS referrer TEXT,
    ADD COLUMN IF NOT EXISTS consentimiento_version TEXT;

ALTER TABLE public.leads_ikki
    DROP CONSTRAINT IF EXISTS leads_ikki_embudo_check;
ALTER TABLE public.leads_ikki
    ADD CONSTRAINT leads_ikki_embudo_check
    CHECK (embudo IN ('B2C', 'B2B'));

ALTER TABLE public.leads_ikki
    DROP CONSTRAINT IF EXISTS leads_ikki_tipo_lead_check;
ALTER TABLE public.leads_ikki
    ADD CONSTRAINT leads_ikki_tipo_lead_check
    CHECK (
        tipo_lead IS NULL
        OR tipo_lead IN (
            'paciente', 'familiar', 'clinica', 'laboratorio',
            'centro_medico', 'otro'
        )
    );

CREATE INDEX IF NOT EXISTS idx_leads_ikki_cliente_embudo_fecha
    ON public.leads_ikki (cliente_id, embudo, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_leads_ikki_origen_plataforma
    ON public.leads_ikki (origen_plataforma, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_leads_ikki_origen_campana
    ON public.leads_ikki (origen_campana);

CREATE INDEX IF NOT EXISTS idx_leads_ikki_utm_campaign
    ON public.leads_ikki (utm_campaign);

COMMENT ON COLUMN public.leads_ikki.cliente_id IS
    'Cliente o marca que recibe el lead; permite separar Gestalt Medical de otros clientes.';
COMMENT ON COLUMN public.leads_ikki.embudo IS
    'Embudo de origen del lead: B2C (paciente/familia) o B2B (institución clínica).';
COMMENT ON COLUMN public.leads_ikki.tipo_lead IS
    'Segmento específico: paciente, familiar, clinica, laboratorio, centro_medico u otro.';
COMMENT ON COLUMN public.leads_ikki.origen_plataforma IS
    'Plataforma de adquisición: meta, google, linkedin, organico, referido, evento u otro.';
COMMENT ON COLUMN public.leads_ikki.utm_source IS
    'Procedencia explícita para reportes de atribución; complementa el JSONB utm.';

-- La columna heredada "fuente" se conserva por compatibilidad.
-- El repositorio escribe en ella el mismo valor de origen_plataforma.


-- ============================================================
-- 3. PRESUPUESTOS MENSUALES DE PAUTA
-- ============================================================

CREATE TABLE IF NOT EXISTS public.presupuestos_ikki (
    id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    grupo_simulacion_id      UUID NOT NULL,
    cliente_id               TEXT NOT NULL,
    periodo_mes              DATE NOT NULL,
    embudo                   TEXT NOT NULL,
    presupuesto_pauta_clp    NUMERIC(14,2) NOT NULL DEFAULT 0,
    fee_fijo_clp             NUMERIC(14,2) NOT NULL DEFAULT 0,
    pct_pauta                NUMERIC(5,4)  NOT NULL DEFAULT 0.1500,
    comision_agencia_clp     NUMERIC(14,2) NOT NULL DEFAULT 0,
    total_facturar_clp       NUMERIC(14,2) NOT NULL DEFAULT 0,
    margen_agencia_clp       NUMERIC(14,2) NOT NULL DEFAULT 0,
    gasto_real_clp           NUMERIC(14,2) NOT NULL DEFAULT 0,
    leads_objetivo           INTEGER NOT NULL DEFAULT 0,
    estado                   TEXT NOT NULL DEFAULT 'simulado',
    metadatos                JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at               TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT presupuestos_ikki_embudo_check
        CHECK (embudo IN ('B2C', 'B2B')),
    CONSTRAINT presupuestos_ikki_periodo_check
        CHECK (periodo_mes = date_trunc('month', periodo_mes)::date),
    CONSTRAINT presupuestos_ikki_presupuesto_check
        CHECK (presupuesto_pauta_clp >= 0),
    CONSTRAINT presupuestos_ikki_fee_check
        CHECK (fee_fijo_clp >= 0),
    CONSTRAINT presupuestos_ikki_pct_check
        CHECK (pct_pauta >= 0 AND pct_pauta <= 1),
    CONSTRAINT presupuestos_ikki_comision_check
        CHECK (comision_agencia_clp >= 0),
    CONSTRAINT presupuestos_ikki_total_check
        CHECK (total_facturar_clp >= 0),
    CONSTRAINT presupuestos_ikki_margen_check
        CHECK (margen_agencia_clp >= 0),
    CONSTRAINT presupuestos_ikki_gasto_check
        CHECK (gasto_real_clp >= 0),
    CONSTRAINT presupuestos_ikki_leads_check
        CHECK (leads_objetivo >= 0),
    CONSTRAINT presupuestos_ikki_estado_check
        CHECK (estado IN ('simulado', 'aprobado', 'ejecutado', 'cerrado', 'cancelado')),
    CONSTRAINT presupuestos_ikki_metadatos_check
        CHECK (jsonb_typeof(metadatos) = 'object'),
    CONSTRAINT presupuestos_ikki_grupo_embudo_key
        UNIQUE (grupo_simulacion_id, embudo)
);

CREATE INDEX IF NOT EXISTS idx_presupuestos_ikki_cliente_periodo
    ON public.presupuestos_ikki (cliente_id, periodo_mes, embudo);

CREATE INDEX IF NOT EXISTS idx_presupuestos_ikki_estado_periodo
    ON public.presupuestos_ikki (estado, periodo_mes);

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

DROP TRIGGER IF EXISTS trg_presupuestos_ikki_updated_at ON public.presupuestos_ikki;
CREATE TRIGGER trg_presupuestos_ikki_updated_at
    BEFORE UPDATE ON public.presupuestos_ikki
    FOR EACH ROW
    EXECUTE FUNCTION public.ikki_set_updated_at();

COMMENT ON TABLE public.presupuestos_ikki IS
    'Presupuesto mensual de pauta por cliente y embudo, con economía de agencia.';
COMMENT ON COLUMN public.presupuestos_ikki.grupo_simulacion_id IS
    'ID de la simulación que originó el presupuesto; permite upsert idempotente.';
COMMENT ON COLUMN public.presupuestos_ikki.gasto_real_clp IS
    'Gasto real informado por Meta/Google Ads; se actualiza fuera de la simulación.';


-- ============================================================
-- 4. VISTA: presupuesto mensual consolidado y CPL objetivo
-- ============================================================

CREATE OR REPLACE VIEW public.vw_ikki_presupuesto_mensual AS
SELECT
    p.cliente_id,
    p.periodo_mes,
    p.embudo,
    SUM(p.presupuesto_pauta_clp)::NUMERIC(14,2) AS presupuesto_pauta_clp,
    SUM(p.gasto_real_clp)::NUMERIC(14,2) AS gasto_real_clp,
    (SUM(p.presupuesto_pauta_clp) - SUM(p.gasto_real_clp))::NUMERIC(14,2)
        AS presupuesto_disponible_clp,
    SUM(p.fee_fijo_clp)::NUMERIC(14,2) AS fee_fijo_clp,
    SUM(p.comision_agencia_clp)::NUMERIC(14,2) AS comision_agencia_clp,
    SUM(p.total_facturar_clp)::NUMERIC(14,2) AS total_facturar_clp,
    SUM(p.margen_agencia_clp)::NUMERIC(14,2) AS margen_agencia_clp,
    SUM(p.leads_objetivo)::BIGINT AS leads_objetivo,
    CASE
        WHEN SUM(p.leads_objetivo) > 0
        THEN ROUND(SUM(p.presupuesto_pauta_clp) / SUM(p.leads_objetivo), 0)
        ELSE NULL
    END AS cpl_objetivo_clp,
    COUNT(*) FILTER (WHERE p.estado = 'simulado') AS simulaciones,
    MAX(p.updated_at) AS actualizado_en
FROM public.presupuestos_ikki p
WHERE p.estado <> 'cancelado'
GROUP BY p.cliente_id, p.periodo_mes, p.embudo;

COMMENT ON VIEW public.vw_ikki_presupuesto_mensual IS
    'Consolida presupuesto, gasto real y CPL objetivo por cliente, mes y embudo.';

-- Consulta de verificación (opcional):
-- SELECT * FROM public.vw_ikki_presupuesto_mensual
-- WHERE cliente_id = 'gestalt-medical'
-- ORDER BY periodo_mes DESC, embudo;
