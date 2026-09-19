-- Migración: knowledge_items (base de conocimiento del CEO)
-- Fecha: 2026-09-19

CREATE TABLE IF NOT EXISTS knowledge_items (
    id SERIAL PRIMARY KEY,
    source TEXT NOT NULL,
    url TEXT,
    title TEXT,
    autor TEXT,
    contenido TEXT NOT NULL,
    resumen TEXT,
    tags JSONB DEFAULT '[]',
    duracion_seg INTEGER,
    creado_en TIMESTAMPTZ DEFAULT NOW(),
    procesado BOOLEAN DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_knowledge_source
    ON knowledge_items (source);

CREATE INDEX IF NOT EXISTS idx_knowledge_creado
    ON knowledge_items (creado_en DESC);

CREATE INDEX IF NOT EXISTS idx_knowledge_tags
    ON knowledge_items USING GIN (tags);
