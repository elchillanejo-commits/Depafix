-- Migración: soporte de clasificación de rubro y trazabilidad de calidad de dato
-- en precios_serviu, más tabla de reglas para el clasificador (core/auditor_precios_ia.py).
-- Idempotente: seguro de re-ejecutar.

-- 1) precios_serviu: nunca tuvo columna `rubro` (confirmado contra prod, 991 filas
--    sin ella) y no tenía forma de marcar registros que el auditor no pudo clasificar.
ALTER TABLE precios_serviu
    ADD COLUMN IF NOT EXISTS rubro TEXT,
    ADD COLUMN IF NOT EXISTS estado_dato TEXT NOT NULL DEFAULT 'OK';

CREATE INDEX IF NOT EXISTS idx_precios_serviu_rubro ON precios_serviu (rubro);
CREATE INDEX IF NOT EXISTS idx_precios_serviu_estado_dato ON precios_serviu (estado_dato);

COMMENT ON COLUMN precios_serviu.rubro IS
    'Categoría de gasto (Construcción, Electricidad, ...). NULL hasta que auditor_precios_ia.py la clasifique.';
COMMENT ON COLUMN precios_serviu.estado_dato IS
    'OK | ERROR_DATOS. ERROR_DATOS = el auditor no pudo clasificar rubro y/o falta valor_unitario; requiere revisión manual.';

-- 2) reglas_rubros: tabla propia para clasificar rubro de precios_serviu por
--    palabras clave en `item`. Deliberadamente separada de `reglas_contables`
--    (esa tabla ya está en producción y la usa core/auditor_ia.py para clasificar
--    movimientos bancarios en cuentas contables — dominio distinto, no se reutiliza
--    para no arriesgar esa integración existente).
CREATE TABLE IF NOT EXISTS reglas_rubros (
    id SERIAL PRIMARY KEY,
    palabra_clave TEXT NOT NULL,
    rubro TEXT NOT NULL,
    prioridad INT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (palabra_clave, rubro)
);

CREATE INDEX IF NOT EXISTS idx_reglas_rubros_prioridad ON reglas_rubros (prioridad DESC);

COMMENT ON TABLE reglas_rubros IS
    'Reglas de clasificación por palabra clave para poblar precios_serviu.rubro. Consumida por core/auditor_precios_ia.py.';

-- Seed inicial, tomado 1:1 del dict RUBROS ya vigente en Aquiles/scrapers/multi_dia.py,
-- para que el backfill clasifique igual que clasificaría un scrape nuevo.
INSERT INTO reglas_rubros (palabra_clave, rubro, prioridad) VALUES
    ('construcción', 'Construcción', 10),
    ('construccion', 'Construcción', 10),
    ('electricidad', 'Electricidad', 10),
    ('eléctric', 'Electricidad', 10),
    ('electric', 'Electricidad', 9),
    ('fontanería', 'Fontanería', 10),
    ('fontaneria', 'Fontanería', 10),
    ('gasfitería', 'Fontanería', 9),
    ('gasfiteria', 'Fontanería', 9),
    ('gráfica', 'Gráfica', 10),
    ('grafica', 'Gráfica', 10),
    ('publicidad', 'Gráfica', 8),
    ('impresión', 'Gráfica', 8),
    ('impresion', 'Gráfica', 8),
    ('capacitación', 'Capacitación', 10),
    ('capacitacion', 'Capacitación', 10),
    ('formación', 'Capacitación', 8),
    ('formacion', 'Capacitación', 8),
    ('entrenamiento', 'Capacitación', 7)
ON CONFLICT DO NOTHING;
