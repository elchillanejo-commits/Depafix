-- EJECUTAR EN EL SQL EDITOR DE SUPABASE
-- Extiende el esquema de create_tokens_tables.sql para el consumo de tokens
-- por consulta (endpoint /api/consultar).

-- Saldo de tokens disponible por token/usuario
ALTER TABLE tokens
    ADD COLUMN IF NOT EXISTS saldo_actual INTEGER NOT NULL DEFAULT 0;

-- Registro de cada consumo de token (una fila por consulta exitosa)
CREATE TABLE IF NOT EXISTS consumo_tokens (
    id SERIAL PRIMARY KEY,
    token_id INTEGER REFERENCES tokens(id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES usuarios(id) ON DELETE CASCADE,
    cliente_id TEXT,
    query TEXT,
    saldo_resultante INTEGER NOT NULL,
    fecha_consumo TIMESTAMP DEFAULT NOW()
);

ALTER TABLE consumo_tokens ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Usuarios pueden ver su propio consumo" ON consumo_tokens
    FOR SELECT USING (auth.uid() = user_id);
