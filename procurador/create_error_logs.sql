-- ============================================================
-- MÓDULO 02_PROCURADOR — error_logs
-- Ejecutar en: Supabase SQL Editor
-- ============================================================

DROP TABLE IF EXISTS error_logs CASCADE;

CREATE TABLE error_logs (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    modulo      TEXT        NOT NULL,
    funcion     TEXT,
    mensaje     TEXT,
    stack_trace TEXT,
    metadata    JSONB       NOT NULL DEFAULT '{}'::jsonb,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_error_logs_modulo ON error_logs (modulo, created_at DESC);

ALTER TABLE error_logs ENABLE ROW LEVEL SECURITY;

COMMENT ON TABLE error_logs IS
    'Fallos de procesamiento de core/procurador_tool.py. '
    'Revisión manual — ningún proceso automático actúa sobre estas filas.';
