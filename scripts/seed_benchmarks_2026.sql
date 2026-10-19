CREATE TABLE IF NOT EXISTS benchmarks_ads (
    id SERIAL PRIMARY KEY,
    plataforma TEXT NOT NULL,
    industria TEXT NOT NULL,
    cpm_min_clp INTEGER,
    cpm_max_clp INTEGER,
    cpc_min_clp INTEGER,
    cpc_max_clp INTEGER,
    presupuesto_minimo_mes_clp INTEGER,
    fuente TEXT,
    actualizado_en TIMESTAMPTZ DEFAULT NOW()
);

INSERT INTO benchmarks_ads (plataforma, industria, cpm_min_clp, cpm_max_clp, presupuesto_minimo_mes_clp, fuente) VALUES
('Meta', 'Inmobiliaria', 5000, 12000, 300000, 'SomosMaqui 2026'),
('Meta', 'Salud', 3000, 7000, 300000, 'SomosMaqui 2026'),
('Meta', 'Restaurantes', 2000, 4500, 250000, 'SomosMaqui 2026'),
('Meta', 'Ecommerce Moda', 2500, 5000, 400000, 'SomosMaqui 2026'),
('Google', 'Servicios Profesionales', 6000, 15000, 300000, 'Estimación mercado Chile'),
('TikTok', 'General', 3000, 8000, 200000, 'WordStream 2026 (referencia)');

CREATE TABLE IF NOT EXISTS matriz_plataforma (
    id SERIAL PRIMARY KEY,
    rubro TEXT UNIQUE NOT NULL,
    red_principal TEXT NOT NULL,
    red_secundaria TEXT,
    justificacion TEXT NOT NULL
);

INSERT INTO matriz_plataforma (rubro, red_principal, red_secundaria, justificacion) VALUES
('Peluquería', 'Instagram', 'Facebook', 'Alto componente visual (antes/después). Facebook para reseñas del barrio.'),
('Taller Mecánico', 'Google Ads', 'TikTok', 'La gente busca urgencia en Google. TikTok/Reels funciona para mostrar reparaciones.'),
('Clínica Dental', 'Google Ads', 'Meta', 'El paciente busca activamente el servicio. Meta para recordación y ofertas.'),
('Restaurante', 'Instagram', 'TikTok', 'Descubrimiento visual. La gente no busca en Google, se topa con el video.'),
('Inmobiliaria', 'Meta', 'Google Ads', 'Ciclo largo. Meta para generar deseo, Google para capturar la búsqueda.'),
('Ferretería', 'Google Ads', 'Facebook', 'Búsqueda de productos específicos (ej. "fierro 8mm"). Facebook para ofertas locales.');
