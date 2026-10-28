-- ============================================================
-- 10_knowledge_chunks_v2.sql
-- Proyecto: DepaFix — consolidación de RAGs trading + marketing
--
-- Objetivo:
--   Crear una tabla staging con el esquema nuevo y convivir con la tabla
--   knowledge_chunks actual (esquema viejo) durante la migración.
--
--   knowledge_chunks_v2:
--     domain, source_file, course_title, content, chunk_index  (esquema nuevo)
--     entry_id, categoria, embedding, modelo, created_at        (compatibilidad RAG)
--
--   La tabla vieja NO se toca. El corte se hace después de:
--     1. correr ingest/knowledge/migrate_rags.py --embeddings --apply
--        con --target-table knowledge_chunks_v2
--     2. validar conteos y búsquedas
--     3. actualizar src/agencia/rag.py y src/trading/rag_helper.py
--        para llamar a match_knowledge_v2
--
--   embedding queda NULLABLE a propósito: permite migrar texto primero y
--   generar/copiar embeddings después. match_knowledge_v2 ignora NULL.
--
-- Idempotente: CREATE ... IF NOT EXISTS / CREATE OR REPLACE.
-- Script local. Correr en el SQL Editor de Supabase.
-- ============================================================

CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA extensions;

-- 1. Tabla staging
CREATE TABLE IF NOT EXISTS public.knowledge_chunks_v2 (
    id          BIGSERIAL PRIMARY KEY,
    entry_id    INTEGER NOT NULL REFERENCES public.knowledge_entries(id) ON DELETE CASCADE,
    domain      TEXT NOT NULL CHECK (domain IN ('trading', 'marketing')),
    source_file TEXT NOT NULL,
    course_title TEXT,
    content     TEXT NOT NULL,
    chunk_index INTEGER NOT NULL CHECK (chunk_index > 0),
    categoria   TEXT,
    modelo      TEXT NOT NULL DEFAULT 'intfloat/multilingual-e5-small',
    embedding   extensions.vector(384),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_knowledge_chunks_v2_source_chunk
        UNIQUE (domain, source_file, chunk_index)
);

CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_v2_domain
    ON public.knowledge_chunks_v2 (domain);

CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_v2_entry
    ON public.knowledge_chunks_v2 (entry_id);

CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_v2_categoria
    ON public.knowledge_chunks_v2 (categoria);

-- Sin índice vectorial todavía: con ~659 filas el scan exacto es rápido.
-- Cuando pase de ~10.000 filas:
--   CREATE INDEX idx_knowledge_chunks_v2_embedding
--     ON public.knowledge_chunks_v2
--     USING hnsw (embedding extensions.vector_cosine_ops);

-- 2. RLS: sin políticas = solo service_role (la API) puede leer/escribir
ALTER TABLE public.knowledge_chunks_v2 ENABLE ROW LEVEL SECURITY;

-- 3. Búsqueda compatible con el RAG actual + filtro por dominio
CREATE OR REPLACE FUNCTION public.match_knowledge_v2(
    query_embedding  extensions.vector(384),
    match_count      INTEGER DEFAULT 3,
    filtro_categoria TEXT    DEFAULT NULL,
    filtro_domain    TEXT    DEFAULT NULL
)
RETURNS TABLE (
    entry_id     INTEGER,
    titulo       CHARACTER VARYING,
    domain       TEXT,
    source_file  TEXT,
    course_title TEXT,
    categoria    TEXT,
    contenido    TEXT,
    similitud    DOUBLE PRECISION
)
LANGUAGE sql
STABLE
SET search_path = public, extensions
AS $$
    WITH ranked AS (
        SELECT c.entry_id,
               c.domain,
               c.source_file,
               c.course_title,
               c.categoria,
               1 - (c.embedding <=> query_embedding) AS similitud,
               row_number() OVER (PARTITION BY c.entry_id
                                  ORDER BY c.embedding <=> query_embedding) AS rn
        FROM public.knowledge_chunks_v2 c
        WHERE c.embedding IS NOT NULL
          AND (filtro_domain IS NULL OR c.domain = filtro_domain)
          AND (filtro_categoria IS NULL OR c.categoria = filtro_categoria)
    )
    SELECT r.entry_id,
           e.titulo,
           r.domain,
           r.source_file,
           r.course_title,
           r.categoria,
           e.contenido,
           r.similitud
    FROM ranked r
    JOIN public.knowledge_entries e ON e.id = r.entry_id
    WHERE r.rn = 1
    ORDER BY r.similitud DESC
    LIMIT match_count;
$$;

REVOKE EXECUTE ON FUNCTION public.match_knowledge_v2(extensions.vector, INTEGER, TEXT, TEXT)
    FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.match_knowledge_v2(extensions.vector, INTEGER, TEXT, TEXT)
    TO service_role;

-- 4. Verificación (debe devolver: knowledge_chunks_v2 | 0)
SELECT to_regclass('public.knowledge_chunks_v2') AS tabla,
       (SELECT count(*) FROM public.knowledge_chunks_v2) AS filas;
