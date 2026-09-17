-- ============================================
-- MIGRACIÓN 02: ÍNDICES Y BÚSQUEDA FULL-TEXT
-- ============================================

-- Índices básicos
CREATE INDEX IF NOT EXISTS idx_licitaciones_estado ON licitaciones(estado);
CREATE INDEX IF NOT EXISTS idx_licitaciones_fecha_cierre ON licitaciones(fecha_cierre);
CREATE INDEX IF NOT EXISTS idx_licitaciones_fecha_publicacion ON licitaciones(fecha_publicacion);
CREATE INDEX IF NOT EXISTS idx_licitaciones_monto ON licitaciones(monto_estimado);
CREATE INDEX IF NOT EXISTS idx_licitaciones_region ON licitaciones(region);
CREATE INDEX IF NOT EXISTS idx_licitaciones_idempotency_key ON licitaciones(idempotency_key);

-- Búsqueda textual (requiere pg_trgm)
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE INDEX IF NOT EXISTS idx_licitaciones_titulo_trgm ON licitaciones USING GIN (titulo gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_licitaciones_descripcion_trgm ON licitaciones USING GIN (descripcion gin_trgm_ops);

-- Función de búsqueda full-text
CREATE OR REPLACE FUNCTION buscar_licitaciones_fts(query_text TEXT)
RETURNS TABLE(
    id BIGINT,
    codigo_licitacion TEXT,
    titulo TEXT,
    organismo TEXT,
    fecha_publicacion DATE,
    fecha_cierre DATE,
    estado TEXT,
    descripcion TEXT,
    palabras_clave JSONB,
    relevancia REAL
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        l.id,
        l.codigo_licitacion,
        l.titulo,
        l.organismo,
        l.fecha_publicacion,
        l.fecha_cierre,
        l.estado,
        l.descripcion,
        l.palabras_clave,
        ts_rank(
            setweight(to_tsvector('spanish', coalesce(l.titulo,'')), 'A') ||
            setweight(to_tsvector('spanish', coalesce(l.descripcion,'')), 'B'),
            plainto_tsquery('spanish', query_text)
        ) AS relevancia
    FROM licitaciones l
    WHERE
        to_tsvector('spanish', coalesce(l.titulo,'') || ' ' || coalesce(l.descripcion,''))
        @@ plainto_tsquery('spanish', query_text)
    ORDER BY relevancia DESC
    LIMIT 100;
END;
$$ LANGUAGE plpgsql;

INSERT INTO migrations_log (migration_name, status) 
VALUES ('02_indices_fts', 'success')
ON CONFLICT (migration_name) DO NOTHING;
