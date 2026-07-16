-- reglas_rubros_exclusiones: guardarraíl de falsos positivos para la
-- clasificación por palabra clave de reglas_rubros. Un ítem que matchea una
-- palabra_clave de un rubro (ej. "construcción" -> Construcción) se descarta
-- para ESE rubro si además contiene alguna palabra excluida (ej. "barco",
-- "pesca") -- caso real: id=560 "Servicios de construcción de barcos o botes
-- de pesca" (valor $6.700.000.000) se clasificó como Construcción y sesgó el
-- promedio/stddev de todo el rubro en v_analisis_desviacion.
--
-- Es una tabla separada (no una columna array en reglas_rubros) porque la
-- exclusión es a nivel de RUBRO, no de una fila/keyword puntual: aplica sin
-- importar cuál palabra_clave fue la que matcheó.
CREATE TABLE IF NOT EXISTS reglas_rubros_exclusiones (
    id SERIAL PRIMARY KEY,
    rubro TEXT NOT NULL,
    palabra_excluida TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (rubro, palabra_excluida)
);

COMMENT ON TABLE reglas_rubros_exclusiones IS
    'Palabras que invalidan un match de reglas_rubros para ese rubro (evita falsos positivos como "construcción de barcos" -> Construcción). Consumida por core/auditor_precios_ia.py.';

INSERT INTO reglas_rubros_exclusiones (rubro, palabra_excluida) VALUES
    ('Construcción', 'barco'),
    ('Construcción', 'bote'),
    ('Construcción', 'naval'),
    ('Construcción', 'pesca'),
    ('Construcción', 'pesquero'),
    ('Construcción', 'marítimo'),
    ('Construcción', 'maritimo'),
    ('Construcción', 'embarcación'),
    ('Construcción', 'embarcacion'),
    ('Construcción', 'buque')
ON CONFLICT DO NOTHING;
