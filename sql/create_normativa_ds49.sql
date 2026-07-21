-- ============================================================
-- Normativa de construcción: decretos, artículos y materiales.
-- Cubre D.S. N°49/2011 (Programa Fondo Solidario de Elección de
-- Vivienda) y su Itemizado Técnico de Construcción (Res. 7713/2017).
--
-- NOTA: material_id referencia line_items(line_item_id), que es
-- UUID en producción (ver 02_DATOS/supabase_schema.sql, verificado
-- por introspección 2026-07-12). El borrador original usaba
-- "line_items(id) INT", columna que no existe -- se corrigió aquí.
-- ============================================================

-- Tabla de decretos / documentos normativos
CREATE TABLE IF NOT EXISTS decretos (
    id SERIAL PRIMARY KEY,
    codigo VARCHAR(20) NOT NULL UNIQUE,
    nombre VARCHAR(200),
    fecha_publicacion DATE,
    descripcion TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Tabla de artículos / secciones
CREATE TABLE IF NOT EXISTS decreto_articulos (
    id SERIAL PRIMARY KEY,
    decreto_id INT REFERENCES decretos(id) ON DELETE CASCADE,
    numero VARCHAR(20) NOT NULL,
    titulo TEXT,
    texto TEXT NOT NULL,
    materia VARCHAR(100),
    fecha_vigencia DATE,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(decreto_id, numero)
);

-- Tabla de materiales vinculados a un artículo/sección
CREATE TABLE IF NOT EXISTS decreto_materiales (
    id SERIAL PRIMARY KEY,
    articulo_id INT REFERENCES decreto_articulos(id) ON DELETE CASCADE,
    material_nombre VARCHAR(200) NOT NULL,
    material_id UUID REFERENCES line_items(line_item_id) NULL,
    requisito TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Índices para rendimiento
CREATE INDEX IF NOT EXISTS idx_decreto_articulos_numero ON decreto_articulos(numero);
CREATE INDEX IF NOT EXISTS idx_decreto_materiales_nombre ON decreto_materiales(material_nombre);
