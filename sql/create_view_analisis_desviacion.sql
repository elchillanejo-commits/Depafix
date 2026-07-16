-- Vista v_analisis_desviacion: promedio y desviación estándar de precio (en CLP)
-- por rubro, para que trade_agent.py haga solo una consulta liviana en vez de
-- traer todas las filas y calcular las estadísticas del lado de Python.
--
-- Reglas aplicadas:
--   - Solo filas estado_dato='OK' (rubro clasificado con confianza; ver
--     core/auditor_precios_ia.py). Las filas ERROR_DATOS quedan fuera.
--   - Solo rubros que existen en reglas_rubros (los "rubros críticos" del
--     negocio) -- así se descarta el ruido de ítems ajenos (equipos de
--     laboratorio, insumos médicos, etc.) que trajo el scraper.
--   - Conversión UF->CLP inline: los registros fuente=SERVIU/SERVIU_DS27_RM_2025
--     están en UF y los de MERCADO_PUBLICO en CLP (confirmado contra datos
--     reales). Sin esta conversión, un mismo rubro puede terminar mezclando
--     valores en UF (~0.1-10) con valores en CLP (~10^5-10^7), lo que rompe
--     cualquier promedio/desviación. Mismo factor que usa
--     core/predict_logic.py (UF_REFERENCIA_SERVIU) -- si ese valor cambia,
--     hay que actualizarlo también acá.
CREATE OR REPLACE VIEW v_analisis_desviacion AS
SELECT
    rubro,
    COUNT(*)                                   AS n_muestras,
    ROUND(AVG(valor_clp)::numeric, 2)          AS promedio_clp,
    ROUND(COALESCE(STDDEV_SAMP(valor_clp), 0)::numeric, 2) AS stddev_clp,
    ROUND(MIN(valor_clp)::numeric, 2)          AS min_clp,
    ROUND(MAX(valor_clp)::numeric, 2)          AS max_clp,
    MAX(created_at)                            AS ultima_actualizacion
FROM (
    SELECT
        rubro,
        created_at,
        CASE WHEN moneda = 'UF' THEN valor_unitario * 38377.09 ELSE valor_unitario END AS valor_clp
    FROM precios_serviu
    WHERE estado_dato = 'OK'
      AND rubro IS NOT NULL
      AND valor_unitario IS NOT NULL
      AND rubro IN (SELECT DISTINCT rubro FROM reglas_rubros)
) sub
GROUP BY rubro;

COMMENT ON VIEW v_analisis_desviacion IS
    'Promedio/stddev de precio en CLP por rubro crítico (rubros definidos en reglas_rubros), solo filas estado_dato=OK. Consumida por core/trade_agent.py.';
