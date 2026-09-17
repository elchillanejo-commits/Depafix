-- ============================================
-- MIGRACIÓN 05: ANÁLISIS AVANZADO (Vistas y funciones)
-- ============================================

-- Vista de alertas pendientes
CREATE OR REPLACE VIEW vw_alertas_pendientes AS
SELECT 
    s.id AS suscripcion_id,
    s.cliente_nombre,
    s.cliente_email,
    s.palabras_clave,
    s.frecuencia_horas,
    s.ultimo_envio,
    COUNT(l.id) AS licitaciones_pendientes
FROM suscripciones s
CROSS JOIN licitaciones l
WHERE s.activo = TRUE
    AND l.created_at > COALESCE(s.ultimo_envio, '1970-01-01')
    AND (
        EXISTS (
            SELECT 1 FROM unnest(s.palabras_clave) AS palabra
            WHERE 
                l.titulo ILIKE '%' || palabra || '%'
                OR l.descripcion ILIKE '%' || palabra || '%'
        )
    )
    AND NOT EXISTS (
        SELECT 1 FROM alertas_enviadas ae
        WHERE ae.suscripcion_id = s.id
        AND ae.licitacion_id = l.id
    )
GROUP BY s.id, s.cliente_nombre, s.cliente_email, s.palabras_clave, 
         s.frecuencia_horas, s.ultimo_envio;

-- Vista de empresas analizadas
CREATE TABLE IF NOT EXISTS empresas_analizadas (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    rut TEXT UNIQUE NOT NULL,
    razon_social TEXT,
    nombre_fantasia TEXT,
    tipo_empresa TEXT,
    region TEXT,
    ultima_actualizacion TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO migrations_log (migration_name, status) 
VALUES ('05_analisis_avanzado', 'success')
ON CONFLICT (migration_name) DO NOTHING;
