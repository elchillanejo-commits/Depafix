CREATE TABLE IF NOT EXISTS public.knowledge_derivatives (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chunk_id UUID NOT NULL REFERENCES public.knowledge_chunks_v2(id) ON DELETE CASCADE,
    type TEXT NOT NULL,
    content TEXT NOT NULL,
    generated_by TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_knowledge_derivatives_chunk_id
    ON public.knowledge_derivatives (chunk_id);

CREATE INDEX IF NOT EXISTS idx_knowledge_derivatives_type
    ON public.knowledge_derivatives (type);

CREATE UNIQUE INDEX IF NOT EXISTS uq_knowledge_derivatives_chunk_type
    ON public.knowledge_derivatives (chunk_id, type);

ALTER TABLE public.knowledge_derivatives ENABLE ROW LEVEL SECURITY;
