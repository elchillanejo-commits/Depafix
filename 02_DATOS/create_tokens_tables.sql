-- EJECUTAR EN EL SQL EDITOR DE SUPABASE
-- Tabla de usuarios
CREATE TABLE IF NOT EXISTS usuarios (
    id SERIAL PRIMARY KEY,
    nombre TEXT,
    email TEXT UNIQUE,
    password TEXT
);

-- Tabla de tokens
CREATE TABLE IF NOT EXISTS tokens (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES usuarios(id) ON DELETE CASCADE,
    token_code TEXT UNIQUE,
    consultas_restantes INTEGER DEFAULT 0,
    fecha_compra TIMESTAMP DEFAULT NOW(),
    fecha_expiracion TIMESTAMP DEFAULT NOW() + INTERVAL '1 year',
    estado TEXT DEFAULT 'activo'
);

-- Tabla de consultas
CREATE TABLE IF NOT EXISTS consultas (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES usuarios(id) ON DELETE CASCADE,
    token_id INTEGER REFERENCES tokens(id) ON DELETE SET NULL,
    tipo_consulta TEXT NOT NULL,
    detalle TEXT,
    fecha_consulta TIMESTAMP DEFAULT NOW()
);

-- Políticas RLS (seguridad)
ALTER TABLE usuarios ENABLE ROW LEVEL SECURITY;
ALTER TABLE tokens ENABLE ROW LEVEL SECURITY;
ALTER TABLE consultas ENABLE ROW LEVEL SECURITY;

-- Políticas básicas (ajusta según tu auth)
CREATE POLICY "Usuarios pueden ver su propio perfil" ON usuarios FOR SELECT USING (auth.uid() = id);
CREATE POLICY "Usuarios pueden ver sus tokens" ON tokens FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Usuarios pueden ver sus consultas" ON consultas FOR SELECT USING (auth.uid() = user_id);
