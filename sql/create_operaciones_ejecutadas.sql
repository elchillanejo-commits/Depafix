CREATE TABLE IF NOT EXISTS operaciones_ejecutadas (
    id SERIAL PRIMARY KEY,
    activo TEXT NOT NULL,
    temporalidad TEXT NOT NULL,
    senal TEXT NOT NULL,
    precio_entrada NUMERIC,
    precio_salida NUMERIC,
    cantidad NUMERIC,
    motivo TEXT,
    ejecutada BOOLEAN DEFAULT false,
    timestamp TIMESTAMPTZ DEFAULT now()
);
