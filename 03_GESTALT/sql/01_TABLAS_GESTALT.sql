-- ========================================
-- Tablas para proyecto GESTALT
-- ========================================
CREATE TABLE IF NOT EXISTS presupuestos (
    id SERIAL PRIMARY KEY,
    cliente VARCHAR(100),
    monto_total DECIMAL(15,2),
    fecha_emision DATE,
    estado VARCHAR(20)
);

CREATE TABLE IF NOT EXISTS records (
    id SERIAL PRIMARY KEY,
    tabla_origen VARCHAR(50),
    registro_id INT,
    accion VARCHAR(20),
    usuario VARCHAR(50),
    fecha TIMESTAMP DEFAULT NOW()
);
