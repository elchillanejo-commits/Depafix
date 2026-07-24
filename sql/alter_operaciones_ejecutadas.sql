-- ==================================================
-- ALTER TABLE para operaciones_ejecutadas
-- Agrega columnas que TradingOrchestrator espera
-- ==================================================

-- Verificar si la columna precio_entrada existe
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'operaciones_ejecutadas' AND column_name = 'precio_entrada') THEN
        ALTER TABLE operaciones_ejecutadas ADD COLUMN precio_entrada NUMERIC;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'operaciones_ejecutadas' AND column_name = 'precio_salida') THEN
        ALTER TABLE operaciones_ejecutadas ADD COLUMN precio_salida NUMERIC;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'operaciones_ejecutadas' AND column_name = 'cantidad') THEN
        ALTER TABLE operaciones_ejecutadas ADD COLUMN cantidad NUMERIC;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'operaciones_ejecutadas' AND column_name = 'motivo') THEN
        ALTER TABLE operaciones_ejecutadas ADD COLUMN motivo TEXT;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'operaciones_ejecutadas' AND column_name = 'puntuacion_confluencia') THEN
        ALTER TABLE operaciones_ejecutadas ADD COLUMN puntuacion_confluencia INT;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'operaciones_ejecutadas' AND column_name = 'timestamp') THEN
        ALTER TABLE operaciones_ejecutadas ADD COLUMN timestamp TIMESTAMPTZ DEFAULT now();
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'operaciones_ejecutadas' AND column_name = 'activo') THEN
        ALTER TABLE operaciones_ejecutadas ADD COLUMN activo TEXT;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'operaciones_ejecutadas' AND column_name = 'temporalidad') THEN
        ALTER TABLE operaciones_ejecutadas ADD COLUMN temporalidad TEXT;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'operaciones_ejecutadas' AND column_name = 'senal') THEN
        ALTER TABLE operaciones_ejecutadas ADD COLUMN senal TEXT;
    END IF;
END $$;

-- Índices
CREATE INDEX IF NOT EXISTS idx_operaciones_activo_timestamp ON operaciones_ejecutadas(activo, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_operaciones_senal ON operaciones_ejecutadas(senal);
