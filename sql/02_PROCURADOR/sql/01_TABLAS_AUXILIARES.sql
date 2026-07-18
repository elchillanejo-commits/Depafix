-- ========================================
-- Tablas para Procurador Virtual
-- ========================================
CREATE TABLE IF NOT EXISTS compliance_logs (
    id SERIAL PRIMARY KEY,
    rol VARCHAR(50),
    etapa_procesal VARCHAR(100),
    riesgo_detectado TEXT,
    dictamen VARCHAR(50),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW()
);

COMMENT ON TABLE compliance_logs IS 'Registros de análisis de compliance para el Procurador Virtual';

-- ========================================
-- Tabla: error_logs (puede ir aquí o en monitoreo)
-- ========================================
CREATE TABLE IF NOT EXISTS error_logs (
    id SERIAL PRIMARY KEY,
    modulo VARCHAR(50),
    funcion VARCHAR(100),
    mensaje TEXT,
    stack_trace TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW()
);

COMMENT ON TABLE error_logs IS 'Bitácora de errores de todos los agentes';
