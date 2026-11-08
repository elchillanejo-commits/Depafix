# ROADMAP Proyecto — Cotizador DepaFix

**Última actualización:** 2026-11-07 14:17 -03 (Supervisor)

## Estado de fases

- **Fase 1 (Scraper 1 producto):** COMPLETADA.
- **Fase 2 (Scraping masivo + PDF multipartida):** EN PROCESO.
  - `@build-data`: scraping masivo/diario (instrucciones asignadas; auditoría de datos realizada 2026-11-07).
  - `@build-pdf` (`@build-docs`): soporte de múltiples materiales en un mismo PDF (instrucciones asignadas).

## Pendientes técnicos

| Pendiente | Estado | Notas |
|---|---|---|
| Integración Evolution API (WhatsApp/automatización) | Pausada | Retomar tras estabilizar cotizador/scraping. |
| Filtro `es_valido=true` en `obtener_ultimo_precio` (`src/data/cotizador.py`) | Pendiente | Recomendado tras ejecutar `scripts/fix_precios_invalidos.sql`; hoy no filtra precios inválidos. |
| Revisión registro colado `SODIMAC-SIN-SKU` ($4, servicio instalación) | Pendiente | Endurecer `candidato_valido` en `scraper_sodimac.py` y limpiar registro (id=7). |
| Restricción `UNIQUE` en BD para `(sku, retailer_id)` / validación scraper | Pendiente | Prevenir duplicados futuros (hoy 0 duplicados). |
| Inconsistencia margen 35% (`proyecto_materiales`) vs 30% (cotizador pinturas) | Pendiente | Alinear regla de negocio o documentar diferencia por módulo. |

## Registro de auditorías

- **2026-11-07 (build-data):** Auditoría Supabase — 0 SKUs duplicados, 0 precios `0/NULL`, 1 precio sospechoso (`SODIMAC-SIN-SKU`, $4). Scripts generados: `scripts/fix_sku_duplicados.sql`, `scripts/fix_precios_invalidos.sql`. Documentación: `docs/DATA_ROADMAP.md`. Salud BD: 🟢 verde en puntos críticos.

## Próximos hitos

1. Confirmar finalización de `@build-data` (scraping masivo/diario) y `@build-pdf` (PDF multipartida).
2. Pruebas de integración: scrape → BD → cotización → PDF multipartida.
3. Ejecutar scripts SQL de limpieza/validación tras respaldo (cuando aplique).
4. Retomar Evolution API.
