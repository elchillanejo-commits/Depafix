-- ============================================================================
-- fix_sku_duplicados.sql
-- DepaFix — Limpieza de SKU duplicados en public.productos
-- ============================================================================
-- Objetivo: dejar un solo producto por SKU, conservando el más reciente.
-- Criterio de "más reciente": created_at DESC (no existe columna updated_at),
-- y id DESC como desempate.
-- Seguridad: idempotente. Si se ejecuta dos veces, la segunda no borra nada
-- porque ya no quedan duplicados (rn > 1 devuelve vacío).
-- ============================================================================

WITH duplicados AS (
    SELECT
        id,
        sku,
        created_at,
        ROW_NUMBER() OVER (
            PARTITION BY sku
            ORDER BY created_at DESC NULLS LAST, id DESC
        ) AS rn
    FROM public.productos
    WHERE sku IS NOT NULL AND sku <> ''
)
DELETE FROM public.productos
WHERE id IN (SELECT id FROM duplicados WHERE rn > 1);

-- Consulta de verificación (ejecutar por separado para auditar antes/despues):
-- SELECT sku, count(*) AS n
-- FROM public.productos
-- WHERE sku IS NOT NULL AND sku <> ''
-- GROUP BY sku
-- HAVING count(*) > 1
-- ORDER BY n DESC;
