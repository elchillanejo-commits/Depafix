-- ============================================================
-- 08_casos_exito_extend.sql
-- Proyecto: DepaFix / Agencia Ikki
--
-- Objetivo:
--   Extender casos_exito (creada por scripts/insert_caso_real.sql) con el
--   schema objetivo, manteniendo las columnas que hoy leen motor_ikki.py y
--   dashboard.py (industria, plataforma, cpl_promedio_clp,
--   mejor_creatividad, descripcion, fuente).
--
-- Idempotente: solo ADD COLUMN IF NOT EXISTS / CREATE ... IF NOT EXISTS.
-- Script local. NO ejecutado contra Supabase.
-- ============================================================

CREATE TABLE IF NOT EXISTS public.casos_exito (
    id SERIAL PRIMARY KEY
);

ALTER TABLE public.casos_exito
    ADD COLUMN IF NOT EXISTS slug              TEXT,         -- clave natural de idempotencia
    ADD COLUMN IF NOT EXISTS cliente           TEXT,
    ADD COLUMN IF NOT EXISTS industria         TEXT,
    ADD COLUMN IF NOT EXISTS plataforma        TEXT,
    ADD COLUMN IF NOT EXISTS problema          TEXT,
    ADD COLUMN IF NOT EXISTS solucion          TEXT,
    ADD COLUMN IF NOT EXISTS resultados        TEXT,
    ADD COLUMN IF NOT EXISTS metricas          JSONB NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS fecha             DATE,
    ADD COLUMN IF NOT EXISTS fuente_archivo    TEXT,
    ADD COLUMN IF NOT EXISTS tipo              TEXT NOT NULL DEFAULT 'real',  -- 'real' | 'estimacion'
    -- Compatibilidad con motor_ikki.py / dashboard.py
    ADD COLUMN IF NOT EXISTS cpl_promedio_clp  INTEGER,
    ADD COLUMN IF NOT EXISTS mejor_creatividad TEXT,
    ADD COLUMN IF NOT EXISTS descripcion       TEXT,
    ADD COLUMN IF NOT EXISTS fuente            TEXT,
    ADD COLUMN IF NOT EXISTS created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    ADD COLUMN IF NOT EXISTS updated_at        TIMESTAMPTZ NOT NULL DEFAULT now();

-- Requerido por el upsert de src/agencia/importar_casos.py (on_conflict=slug).
CREATE UNIQUE INDEX IF NOT EXISTS uq_casos_exito_slug
    ON public.casos_exito (slug);

CREATE INDEX IF NOT EXISTS idx_casos_exito_industria
    ON public.casos_exito (industria);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'chk_casos_exito_tipo'
    ) THEN
        ALTER TABLE public.casos_exito
            ADD CONSTRAINT chk_casos_exito_tipo CHECK (tipo IN ('real', 'estimacion'));
    END IF;
END;
$$;


-- ============================================================
-- BACKFILL de filas existentes (cargadas por scripts/insert_caso_real.sql)
-- Asigna el mismo slug que calcula importar_casos.py para que el upsert
-- actualice estas filas en vez de duplicarlas. Idempotente (WHERE slug IS NULL).
-- ============================================================
UPDATE public.casos_exito
   SET slug = 'cordillera-inmobiliaria-meta-video-testimonio',
       cliente = 'Cordillera',
       tipo = 'real'
 WHERE slug IS NULL
   AND fuente = 'Caso Cordillera - Chile 2026'
   AND plataforma = 'Meta'
   AND mejor_creatividad = 'Video Testimonio';

UPDATE public.casos_exito
   SET slug = 'mercado-inmobiliaria-google-busqueda-de-marca',
       tipo = 'estimacion'
 WHERE slug IS NULL
   AND fuente = 'Estimación Mercado Chile'
   AND plataforma = 'Google'
   AND mejor_creatividad = 'Búsqueda de Marca';

-- Verificación: debe devolver 0 filas.
SELECT id, industria, plataforma, fuente
  FROM public.casos_exito
 WHERE slug IS NULL;
