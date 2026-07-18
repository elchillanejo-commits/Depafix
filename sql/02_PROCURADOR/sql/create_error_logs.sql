-- error_logs: registro de fallos de procesamiento de core/procurador_tool.py
-- (PDF ilegible, insert a compliance_logs agotando reintentos, etc.), para
-- que un humano los revise -- ningun proceso automatizado actua sobre estas
-- filas por si solo (ver discusion en el chat: se descarto explicitamente
-- un loop autonomo que invocara un agente de IA al fallar).

CREATE TABLE IF NOT EXISTS error_logs (
    id BIGSERIAL PRIMARY KEY,
    proceso TEXT NOT NULL,
    codigo_error TEXT,
    archivo TEXT,
    mensaje TEXT,
    detalle JSONB,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_error_logs_lookup
    ON error_logs (proceso, created_at DESC);

COMMENT ON TABLE error_logs IS
    'Fallos de procesamiento por proceso (ej. "procurador_tool"): codigo_error + archivo afectado + mensaje + detalle JSONB con el contexto completo. Revision manual -- ver core/procurador_tool.py para el punto de escritura.';

-- Mismo patron que el resto del repo: RLS activado sin policy, escritura
-- solo con SUPABASE_SERVICE_ROLE_KEY.
ALTER TABLE error_logs ENABLE ROW LEVEL SECURITY;
