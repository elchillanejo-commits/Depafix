-- Datos reales extraídos de una campaña inmobiliaria (Cordillera) en Chile
CREATE TABLE IF NOT EXISTS casos_exito (
    id SERIAL PRIMARY KEY,
    industria TEXT,
    plataforma TEXT,
    cpl_promedio_clp INTEGER,
    mejor_creatividad TEXT,
    descripcion TEXT,
    fuente TEXT
);

INSERT INTO casos_exito (industria, plataforma, cpl_promedio_clp, mejor_creatividad, descripcion, fuente) VALUES
('Inmobiliaria', 'Meta', 7688, 'Video Testimonio', '1.562 leads generados con $14.4M. El video testimonio cerró 11 ventas reales.', 'Caso Cordillera - Chile 2026'),
('Inmobiliaria', 'Google', 12000, 'Búsqueda de Marca', 'Campañas de búsqueda capturan a quienes ya buscan la constructora. Alta intención.', 'Estimación Mercado Chile');
