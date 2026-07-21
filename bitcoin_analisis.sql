-- ============================================================
-- COMPLEMENTO - ANÁLISIS DE BITCOIN (Bullrun 2027-2028)
-- Fuente: "Las Élites de BITCOIN Están Preparando el BULLRUN 2027"
-- ============================================================

INSERT INTO solana_analysis (metric_category, metric_name, metric_value, metric_numeric, unit, context) VALUES

-- PRECIOS CLAVE Y OBJETIVOS
('Bitcoin', 'Precio actual (referencia)', '$60,000', 60000.0000, 'USD', 'Precio desde el cual Bitcoin podría recuperarse hacia 85k'),
('Bitcoin', 'Objetivo mínimo post-recuperación', '$85,000', 85000.0000, 'USD', 'Mínimo esperado tras superar los 60k en el próximo ciclo alcista'),
('Bitcoin', 'Precio realizado del operador de largo plazo (LTH)', '$49,000', 49000.0000, 'USD', 'Nivel clave que suele perderse en los mínimos de ciclo; zona de compra'),
('Bitcoin', 'Posible zona de mechazo (capitulación final)', '$44,000 - $47,000', NULL, 'USD', 'Rango estimado para el último coletazo bajista antes de revertir'),

-- MÉTRICAS ON-CHAIN
('On-Chain', 'Holders de largo plazo (LTH) - tendencia', 'Aumentando tenencias', NULL, NULL, 'Línea azul: los operadores de largo plazo están acumulando en zonas bajas'),
('On-Chain', 'Nuevo dinero entrante (STH) - tendencia', 'En mínimos de varios años', NULL, NULL, 'Línea roja: el interés de nuevo capital está en niveles de fondo de ciclo'),
('On-Chain', 'Sentimiento del LTH (índice de miedo)', 'En miedo, sin llegar a punto cero', NULL, NULL, 'Falta la capitulación final del LTH para confirmar el mínimo absoluto'),

-- INTERÉS Y SENTIMIENTO
('Sentimiento', 'Interés general en Bitcoin', 'En niveles de mínimos de 2011, 2015 y 2018', NULL, NULL, 'Métrica compuesta que indica desinterés propio de zonas de acumulación'),
('Sentimiento', 'Miedo / codicia (Fear & Greed)', 'Miedo', NULL, NULL, 'Indicador en zona de miedo, aún no en pánico extremo'),

-- ESTRATEGIA Y ZONAS DE COMPRA
('Estrategia', 'Zona de compra (alta probabilidad)', 'Por debajo de $49,000', 49000.0000, 'USD', 'Precio realizado del LTH; históricamente mejor zona de compra del ciclo'),
('Estrategia', 'Capitulación final esperada', 'Pérdida del nivel $49,000 y sentimiento LTH en negativo', NULL, NULL, 'Condición necesaria para que los mínimos sean duraderos'),
('Estrategia', 'Estructura de mercado actual', 'Cambio de dinámica: de limpiar cortos a limpiar largos', NULL, NULL, 'Indica que las élites están preparando el terreno para el próximo rally'),

-- ESCENARIOS
('Escenario', 'Escenario base (alcista)', 'Bitcoin a $85,000 como mínimo tras recuperar $60,000', 85000.0000, 'USD', 'Movimiento esperado para el segundo trimestre de 2027'),
('Escenario', 'Escenario de capitulación final', 'Mechazo a $44k-$47k, luego recuperación violenta', NULL, 'USD', 'Manipulación típica antes de revertir la tendencia bajista'),
('Escenario', 'Punto líquido más importante (liquidez bajista)', '$49,000', 49000.0000, 'USD', 'Nivel donde se concentran órdenes de stop-loss; probablemente será cazado'),

-- ANÁLISIS TÉCNICO (PATRONES)
('Análisis Técnico', 'Patrón actual', 'Acumulación → Manipulación → Expansión (WOF)', NULL, NULL, 'Estructura cíclica que precede a grandes movimientos alcistas'),
('Análisis Técnico', 'Estructura correctiva en Ethereum', 'Flat (3-3-5) en zona de resistencia', NULL, NULL, 'Indica que ETH probablemente buscará mínimos por debajo de $1700'),

-- CONCLUSIÓN
('Conclusión', '¿Comprar ahora?', 'Sí, en zona de acumulación, pero no el mínimo', NULL, NULL, 'Las élites están comprando silenciosamente; falta la capitulación final'),
('Conclusión', 'Recomendación final', 'Acumular en DCA por debajo de $49k, guardar liquidez para mechazo a $44k-$47k', NULL, NULL, 'Estrategia para maximizar entrada en el próximo bullrun 2027-2028');
