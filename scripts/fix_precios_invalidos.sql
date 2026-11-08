-- ============================================================================
-- fix_precios_invalidos.sql
-- DepaFix — Precios inválidos en public.precios_historial
-- ============================================================================
-- Objetivo: neutralizar registros con precio_neto NULL o 0 (imposibles de
-- cotizar; harían fallar al motor de cotización o generar presupuestos a $0).
--
-- ENFOQUE ELEGIDO: MARCAR, NO BORRAR (más seguro).
--   * Se agrega la columna es_valido (boolean, default true) si no existe.
--   * Los registros inválidos se pasan a es_valido = false.
--   * El registro se conserva para auditoría y trazabilidad del scraper.
--
-- NOTA PARA EL MOTOR DE COTIZACIÓN:
--   src/data/cotizador.py (función obtener_ultimo_precio) debe filtrar
--   es_valido = true (y precio_neto > 0) al consultar precios_historial.
--   Actualmente no filtra por es_valido; agregarlo previene que un precio
--   inválido futuro sea usado en una cotización.
-- ============================================================================

-- 1) Agregar columna de validez (idempotente)
ALTER TABLE public.precios_historial
    ADD COLUMN IF NOT EXISTS es_valido boolean NOT NULL DEFAULT true;

-- 2) Marcar como inválidos los registros con precio_neto NULL o 0
UPDATE public.precios_historial
SET es_valido = false
WHERE es_valido = true
  AND (precio_neto IS NULL OR precio_neto = 0);

-- 3) Verificación: cuántos inválidos quedaron marcados
-- SELECT count(*) AS invalidos_marcados
-- FROM public.precios_historial
-- WHERE es_valido = false;

-- 4) Verificación: precios sospechosos muy bajos (opcional, revisar manualmente)
-- SELECT id, producto_id, precio_neto, precio_lista, fecha_scrapeo, url_producto
-- FROM public.precios_historial
-- WHERE es_valido = true
--   AND precio_neto > 0
--   AND precio_neto < 1000
-- ORDER BY precio_neto ASC;
