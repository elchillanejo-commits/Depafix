# REPORTE QA — Coaches Agua / Aire / Fuego (Build 2)

## Resultado general: ⚠️ PENDIENTE DE TEST

| Coach | Tabla | RPC | Enfoque principal | Estado | Observaciones |
|-------|-------|-----|------------------|--------|---------------|
| Agua | coach_agua | match_coach_agua | dropshipping, Shopify | ❌ Pendiente de test | Ingestado 477 fragmentos; expectativas: similitud > 0.80 |
| Aire | coach_aire | match_coach_aire | Meta Ads, ROAS | ❌ Pendiente de test | Ingestado 589 fragmentos; expectativas: similitud > 0.80 |
| Fuego | coach_fuego | match_coach_fuego | pentesting, firewall | ❌ Pendiente de test | Ingestado 663 fragmentos; expectativas: similitud > 0.80 |

## Hallazgos (previos)

1. **coach_agua** ✅ — Tabla creada, RPC funcional y devuelve similitud por encima del umbral 0.80.
2. **coach_aire** ❌ — La tabla existe pero no contiene fragmentos insertados (vacía).
3. **coach_fuego** ❌ — La tabla existe pero no contiene fragmentos insertados (vacía).

## Estado actual

- **Agua**: 477 fragmentos ingresados, temas {curso: 122, normativa: 2, tramite: 95, general: 258}
- **Aire**: 589 fragmentos ingresados, temas {curso: 131, normativa: 4, tramite: 68, general: 386}
- **Fuego**: 663 fragmentos ingresados, temas {curso: 148, normativa: 55, tramite: 117, general: 343}

## Próximos pasos

1. Ejecutar el checklist de validación con las 5 preguntas clave (2 Agua, 2 Aire, 1 Fuego).
2. Verificar similitud > 0.80 y relevancia de contenido por coach.
3. Repasar la contaminación cruzada (17 archivos de ecommerce en Fuego).
4. Ingresar los 17 archivos de ecommerce a `coach_aire` o limpiarlos de `coach_fuego`.
5. Ejecutar `test_coaches_rag.py` hasta que los 3 coaches den ✅ PASS.
6. Actualizar este reporte con resultados finales.
