-- compliance_logs: registro de causas judiciales procesadas por
-- core/procurador_tool.py (ROL, tribunal, etapa procesal, litigantes,
-- proximo plazo) junto con el dictamen del motor de riesgo
-- (analyze_legal_risk, ver config/legal_rules.json). Una fila por
-- documento/novedad procesada; idempotency_key evita duplicar la misma
-- novedad si el parser o el cron corren dos veces sobre el mismo PDF/ROL.
--
-- No existen roles "procurador"/"titular" en este proyecto (el unico rol
-- Postgres custom hoy es bi_readonly, ver sql/create_bi_readonly.sql) --
-- se sigue el mismo patron de seguridad que el resto de las tablas del
-- repo: RLS activado sin policy, escritura solo con
-- SUPABASE_SERVICE_ROLE_KEY. Si mas adelante procuradores/titulares deben
-- insertar directo desde el cliente (bypaseando el backend), hace falta
-- definir esos roles primero -- no se improvisan aca.

CREATE TABLE IF NOT EXISTS compliance_logs (
    log_id BIGSERIAL PRIMARY KEY,
    rol TEXT,
    tribunal TEXT,
    etapa_procesal TEXT,
    litigantes JSONB DEFAULT '{}'::jsonb,
    proximo_plazo TEXT,
    document_hash TEXT,
    verdict TEXT NOT NULL DEFAULT 'PENDIENTE'
        CHECK (verdict IN (
            'PENDIENTE', 'REVISION_URGENTE', 'REVISION_MANUAL', 'NEGOCIAR',
            'OBSERVACION_MENOR', 'SIN_OBSERVACIONES', 'APROBADO', 'RECHAZADO'
        )),
    risk_score INTEGER NOT NULL DEFAULT 0,
    critical_risks JSONB DEFAULT '[]'::jsonb,
    safeguard_clauses JSONB DEFAULT '[]'::jsonb,
    raw_analysis JSONB,
    idempotency_key TEXT NOT NULL UNIQUE,
    firm_id UUID,
    record_id UUID,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_compliance_logs_rol
    ON compliance_logs (rol, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_compliance_logs_firm
    ON compliance_logs (firm_id, created_at DESC);

COMMENT ON TABLE compliance_logs IS
    'Causas judiciales procesadas por core/procurador_tool.py: datos extraidos del PDF (rol/tribunal/etapa/litigantes/proximo_plazo) + dictamen del motor de riesgo (verdict/risk_score/critical_risks/safeguard_clauses). idempotency_key = SHA-256 de rol+hash del documento (o rol+novedad para el cron), para no duplicar la misma fila si el proceso corre dos veces.';

ALTER TABLE compliance_logs ENABLE ROW LEVEL SECURITY;
