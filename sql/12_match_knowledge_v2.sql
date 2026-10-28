-- ============================================================
-- 12_match_knowledge_v2.sql
-- RPC de búsqueda vectorial para knowledge_chunks_v2.
--
-- Esquema real de knowledge_chunks_v2:
--   id UUID, domain, source_file, course_title, content,
--   chunk_index, embedding vector(384), created_at, updated_at
--
-- Devuelve chunks directos de v2 (sin join a knowledge_entries, porque
-- el esquema real de v2 no tiene entry_id/categoria).
--
-- Similitud: coseno (1 - distancia coseno). Como los embeddings de
-- multilingual-e5-small están normalizados, el ranking coincide con
-- la distancia euclidiana.
--
-- Ejecutar en el SQL Editor de Supabase. Idempotente.
-- ============================================================

SET search_path = public, extensions;

CREATE OR REPLACE FUNCTION public.match_knowledge_v2(
    query_embedding  vector(384),
    match_count      INTEGER DEFAULT 5,
    filtro_domain    TEXT    DEFAULT NULL
)
RETURNS TABLE (
    id           UUID,
    domain       TEXT,
    source_file  TEXT,
    course_title TEXT,
    chunk_index  INTEGER,
    content      TEXT,
    score        DOUBLE PRECISION
)
LANGUAGE sql
STABLE
SET search_path = public, extensions
AS $$
    SELECT
        c.id,
        c.domain,
        c.source_file,
        c.course_title,
        c.chunk_index,
        c.content,
        1 - (c.embedding <=> query_embedding) AS score
    FROM public.knowledge_chunks_v2 c
    WHERE c.embedding IS NOT NULL
      AND (filtro_domain IS NULL OR c.domain = filtro_domain)
    ORDER BY c.embedding <=> query_embedding
    LIMIT GREATEST(match_count, 0);
$$;

REVOKE EXECUTE ON FUNCTION public.match_knowledge_v2(vector, INTEGER, TEXT)
    FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.match_knowledge_v2(vector, INTEGER, TEXT)
    TO service_role;

NOTIFY pgrst, 'reload schema';

-- Verificación: devuelve 3 chunks de marketing usando un embedding real.
SELECT id, domain, source_file, score
FROM public.match_knowledge_v2(
    (SELECT embedding FROM public.knowledge_chunks_v2
     WHERE embedding IS NOT NULL AND domain = 'marketing' LIMIT 1)::vector(384),
    3,
    'marketing'
);
