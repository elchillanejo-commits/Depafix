-- ============================================
-- MIGRACIÓN 04: SUSCRIPCIONES, ALERTAS Y ANÁLISIS
-- ============================================

-- Suscripciones de clientes
CREATE TABLE IF NOT EXISTS suscripciones (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    cliente_nombre TEXT NOT NULL,
    cliente_email TEXT NOT NULL,
    palabras_clave TEXT[] NOT NULL,
    frecuencia_horas INTEGER DEFAULT 24,
    ultimo_envio TIMESTAMPTZ,
    activo BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- Historial de alertas enviadas
CREATE TABLE IF NOT EXISTS alertas_enviadas (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    suscripcion_id BIGINT NOT NULL REFERENCES suscripciones(id) ON DELETE CASCADE,
    licitacion_id BIGINT NOT NULL REFERENCES licitaciones(id) ON DELETE CASCADE,
    enviado_en TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(suscripcion_id, licitacion_id)
);

-- Historial de pagos
CREATE TABLE IF NOT EXISTS historial_pagos (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    organismo TEXT NOT NULL,
    rut TEXT,
    licitacion_codigo TEXT,
    monto_pagado NUMERIC(15,2),
    fecha_pago DATE,
    dias_mora INTEGER,
    estado_pago TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Precios de referencia
CREATE TABLE IF NOT EXISTS precios_referencia (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    producto TEXT NOT NULL,
    categoria TEXT,
    marca TEXT,
    precio_sodimac NUMERIC(15,2),
    precio_imperial NUMERIC(15,2),
    precio_yolito NUMERIC(15,2),
    precio_promedio NUMERIC(15,2),
    fecha_actualizacion DATE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Análisis de licitaciones
CREATE TABLE IF NOT EXISTS analisis_licitaciones (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    licitacion_id BIGINT REFERENCES licitaciones(id) ON DELETE CASCADE,
    fecha_analisis TIMESTAMPTZ NOT NULL DEFAULT now(),
    riesgo_legal TEXT,
    observaciones TEXT,
    clausulas_riesgosas TEXT[],
    recomendaciones TEXT,
    foda JSONB,
    puntaje_total INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Reportes para contratistas
CREATE TABLE IF NOT EXISTS reportes_contratista (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    contratista_id BIGINT REFERENCES suscripciones(id) ON DELETE CASCADE,
    licitacion_id BIGINT REFERENCES licitaciones(id) ON DELETE CASCADE,
    fecha_generacion TIMESTAMPTZ NOT NULL DEFAULT now(),
    contenido JSONB,
    formato TEXT,
    creado_por TEXT
);

-- Índices
CREATE INDEX IF NOT EXISTS idx_suscripciones_email ON suscripciones(cliente_email);
CREATE INDEX IF NOT EXISTS idx_suscripciones_activo ON suscripciones(activo);
CREATE INDEX IF NOT EXISTS idx_suscripciones_palabras ON suscripciones USING GIN (palabras_clave);
CREATE INDEX IF NOT EXISTS idx_alertas_suscripcion ON alertas_enviadas(suscripcion_id);
CREATE INDEX IF NOT EXISTS idx_alertas_licitacion ON alertas_enviadas(licitacion_id);
CREATE INDEX IF NOT EXISTS idx_historial_pagos_organismo ON historial_pagos(organismo);
CREATE INDEX IF NOT EXISTS idx_precios_referencia_producto ON precios_referencia(producto);

-- Trigger para actualizar updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_suscripciones_updated_at
    BEFORE UPDATE ON suscripciones
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Deshabilitar RLS para reportes
ALTER TABLE reportes_contratista DISABLE ROW LEVEL SECURITY;

INSERT INTO migrations_log (migration_name, status) 
VALUES ('04_suscripciones_alertas', 'success')
ON CONFLICT (migration_name) DO NOTHING;
