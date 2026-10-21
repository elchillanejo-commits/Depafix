-- ============================================================
-- REGLAS DE ORO EXTRAÍDAS DE EXPERTOS (YOUTUBE)
-- ============================================================

CREATE TABLE IF NOT EXISTS reglas_industria (
    id SERIAL PRIMARY KEY,
    plataforma TEXT,
    regla TEXT NOT NULL,
    fuente TEXT
);

INSERT INTO reglas_industria (plataforma, regla, fuente) VALUES
('Meta', 'Presupuesto mínimo recomendado: $300.000 CLP mensuales (~$10.000/día) para salir de la fase de aprendizaje.', 'Felipe Vergara'),
('Google', 'Usar palabras clave negativas ("gratis", "barato") para evitar clics basura y bajar el CPC.', 'Alan Valdez'),
('Meta', 'Para negocios locales (dentistas, ferreterías), usar campañas de "Clientes Potenciales" (Leads) hacia WhatsApp.', 'Felipe Vergara'),
('Google', 'Campañas de Búsqueda (Search) capturan la intención de compra directa. Ideal para servicios urgentes.', 'Ignacio Herrera'),
('Agencia', 'Cobro estándar en Chile: Fee Fijo $150.000 - $250.000 CLP + 15% a 20% de comisión sobre la pauta.', 'Isaac Reyes'),
('Agencia', 'Vender "Garantía de Resultados" (ej. X leads en 30 días). Si no se cumple, se devuelve el fee o se trabaja gratis.', 'Video de Marketing'),
('Meta', 'Dividir el presupuesto en 3-5 conjuntos de anuncios (Ad Sets) con diferentes públicos para testear rápido.', 'Felipe Vergara'),
('Google', 'Configurar correctamente la "Atribución" y las conversiones antes de lanzar la campaña, sino es gastar a ciegas.', 'Alan Valdez');

CREATE TABLE IF NOT EXISTS cotizaciones_competencia (
    id SERIAL PRIMARY KEY,
    tipo_servicio TEXT,
    precio_clp_min INTEGER,
    precio_clp_max INTEGER,
    fuente TEXT
);

INSERT INTO cotizaciones_competencia (tipo_servicio, precio_clp_min, precio_clp_max, fuente) VALUES
('Gestión de 1 canal (Meta o Google)', 100000, 165000, 'Mercado Chile 2026'),
('Gestión Multicanal (Meta + Google)', 400000, 900000, 'Mercado Chile 2026'),
('Fee Fijo Agencia Boutique', 150000, 250000, 'Isaac Reyes (YouTube)');
