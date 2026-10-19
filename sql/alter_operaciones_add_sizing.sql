-- Añade columnas para position_sizer. Idempotente, seguro en prod.
-- Ejecutar en Supabase SQL Editor.
ALTER TABLE public.operaciones_ejecutadas
  ADD COLUMN IF NOT EXISTS posicion_usd NUMERIC(20,2),
  ADD COLUMN IF NOT EXISTS regimen TEXT;

-- Verificación
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_schema='public' AND table_name='operaciones_ejecutadas'
  AND column_name IN ('posicion_usd','regimen');
