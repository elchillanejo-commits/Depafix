-- EJECUTAR EN EL SQL EDITOR DE SUPABASE
-- Tabla de precios referenciales SERVIU/MINVU (DS27), consultada por core/predict_logic.py
CREATE TABLE IF NOT EXISTS precios_serviu (
    id SERIAL PRIMARY KEY,
    item TEXT NOT NULL,
    unidad TEXT,
    valor_unitario NUMERIC NOT NULL,
    fuente TEXT,
    idempotency_key TEXT UNIQUE NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_precios_serviu_item ON precios_serviu (item);
