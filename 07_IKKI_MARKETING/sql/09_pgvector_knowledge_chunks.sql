-- ============================================================
-- 09_pgvector_knowledge_chunks.sql
-- Proyecto: DepaFix / Agencia Ikki — Handoff 006
--
-- Objetivo:
--   Llevar el RAG de videos (hoy en data/conocimiento.faiss local) a Supabase
--   con pgvector, para que la API en Railway pueda consultarlo sin FAISS.
--
--   knowledge_entries  = chunk padre (~700 palabras)     ← ya existe, no se altera
--   knowledge_chunks   = sub-fragmento (~150 palabras) + embedding 384d  ← NUEVA
--
-- Modelo: intfloat/multilingual-e5-small (384d, normalizado).
--   Al indexar se codifica "passage: <texto>", al consultar "query: <texto>".
--
-- Los embeddings NO se pueden calcular en SQL: después de correr este script,
-- cargar los 442 sub-fragmentos con:
--   HF_HUB_OFFLINE=1 venv/bin/python src/agencia/ingestar_videos.py --apply
--
-- Idempotente: CREATE ... IF NOT EXISTS / CREATE OR REPLACE.
-- Script local. Correr en el SQL Editor de Supabase.
-- ============================================================

-- 1. Extensión (Supabase la instala en el schema 'extensions')
CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA extensions;

-- 2. Tabla de sub-fragmentos con su vector
CREATE TABLE IF NOT EXISTS public.knowledge_chunks (
    id          BIGSERIAL PRIMARY KEY,
    entry_id    INTEGER NOT NULL REFERENCES public.knowledge_entries(id) ON DELETE CASCADE,
    sub_index   INTEGER NOT NULL,                 -- posición dentro del chunk padre (1..n)
    texto       TEXT    NOT NULL,                 -- sub-fragmento de ~150 palabras (sin prefijo)
    categoria   TEXT,                             -- copia de knowledge_entries.metadata->>'categoria'
    modelo      TEXT    NOT NULL DEFAULT 'intfloat/multilingual-e5-small',
    embedding   extensions.vector(384) NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_knowledge_chunks_entry_sub UNIQUE (entry_id, sub_index)
);

CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_categoria ON public.knowledge_chunks (categoria);

-- Sin índice vectorial a propósito: con ~450 filas el scan exacto tarda < 5 ms
-- y no pierde resultados al filtrar por categoría (HNSW sí puede perderlos).
-- Cuando pase de ~10.000 filas:
--   CREATE INDEX idx_knowledge_chunks_embedding ON public.knowledge_chunks
--     USING hnsw (embedding extensions.vector_cosine_ops);

-- 3. RLS: sin políticas = solo service_role (la API) puede leer/escribir
ALTER TABLE public.knowledge_chunks ENABLE ROW LEVEL SECURITY;

-- 4. Búsqueda: mejor sub-fragmento por chunk padre, devuelve el padre completo
CREATE OR REPLACE FUNCTION public.match_knowledge(
    query_embedding  extensions.vector(384),
    match_count      INTEGER DEFAULT 3,
    filtro_categoria TEXT    DEFAULT NULL
)
RETURNS TABLE (
    entry_id   INTEGER,
    titulo     CHARACTER VARYING,
    categoria  TEXT,
    contenido  TEXT,
    similitud  DOUBLE PRECISION
)
LANGUAGE sql
STABLE
SET search_path = public, extensions
AS $$
    WITH ranked AS (
        SELECT c.entry_id,
               c.categoria,
               1 - (c.embedding <=> query_embedding) AS similitud,
               row_number() OVER (PARTITION BY c.entry_id
                                  ORDER BY c.embedding <=> query_embedding) AS rn
        FROM public.knowledge_chunks c
        WHERE filtro_categoria IS NULL OR c.categoria = filtro_categoria
    )
    SELECT r.entry_id, e.titulo, r.categoria, e.contenido, r.similitud
    FROM ranked r
    JOIN public.knowledge_entries e ON e.id = r.entry_id
    WHERE r.rn = 1
    ORDER BY r.similitud DESC
    LIMIT match_count;
$$;

REVOKE EXECUTE ON FUNCTION public.match_knowledge(extensions.vector, INTEGER, TEXT) FROM PUBLIC, anon, authenticated;
GRANT  EXECUTE ON FUNCTION public.match_knowledge(extensions.vector, INTEGER, TEXT) TO service_role;

-- 5. Verificación (debe devolver: vector | knowledge_chunks | 0)
SELECT (SELECT extname FROM pg_extension WHERE extname = 'vector') AS extension,
       to_regclass('public.knowledge_chunks')                       AS tabla,
       (SELECT count(*) FROM public.knowledge_chunks)               AS filas;
