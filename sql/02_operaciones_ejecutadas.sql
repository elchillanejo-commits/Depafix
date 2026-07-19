-- 02_operaciones_ejecutadas
CREATE TABLE IF NOT EXISTS operaciones_ejecutadas (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    activo TEXT NOT NULL,
    temporalidad TEXT NOT NULL,
    senal TEXT NOT NULL CHECK (senal IN ('COMPRA', 'VENTA', 'ESPERA')),
    precio_entrada NUMERIC,
    precio_salida NUMERIC,
    cantidad NUMERIC,
    motivo TEXT,
    puntuacion_confluencia INT,
    ejecutada BOOLEAN DEFAULT false,
    timestamp TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_operaciones_activo_timestamp ON operaciones_ejecutadas(activo, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_operaciones_senal ON operaciones_ejecutadas(senal);
CREATE INDEX IF NOT EXISTS idx_operaciones_timestamp ON operaciones_ejecutadas(timestamp);
CREATE INDEX IF NOT EXISTS idx_operaciones_ejecutada ON operaciones_ejecutadas(ejecutada);

ALTER TABLE operaciones_ejecutadas ENABLE ROW LEVEL SECURITY;

CREATE POLICY operaciones_ejecutadas_insert_policy ON operaciones_ejecutadas
    FOR INSERT WITH CHECK (true);

CREATE POLICY operaciones_ejecutadas_select_policy ON operaciones_ejecutadas
    FOR SELECT USING (true);
