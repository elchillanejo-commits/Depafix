# 📋 OBRERO ALMACENES — SPEC LIGERO (DepaFix 3.0)

**Rol:** Obrero de Terreno — Relevamiento de almacenes/competencia.
**Elemento padre:** Tierra (Construcción / SERVIU / Terreno).
**Consumidores downstream:** Profesor Tierra + CEO Informático (Mente 360).

## 1. Identidad y aislamiento
- **Nombre:** `obrero-almacenes` (oficio: relevamiento de almacenes).
- **Aislamiento:** tabla propia `obrero_almacenes_relevamiento`; RLS por `operador`/`comuna`. No toca `cotizaciones`, `franquicia_empresas` ni `knowledge_chunks_v2` directamente.
- **Sin secretos hardcodeados:** claves por env (`DEPAFIX_API_KEY`, `SUPABASE_SERVICE_ROLE_KEY`); endpoints protegidos con `X-API-Key` + rate limit.

## 2. Campos de captura en terreno
| Campo | Tipo | Requerido | Descripción |
|---|---|---|---|
| `almacen` | str | ✅ | Nombre del almacén/competidor |
| `comuna` | str | ✅ | Comuna donde se releva |
| `falla_dolor` | str | ✅ | Falla o dolor detectado (rotura, falta de stock, mala atención, etc.) |
| `producto_estrella_competencia` | str | ✅ | Producto estrella de la competencia observado |
| `precio_clp` | Decimal | ✅ | Precio observado (Decimal + ROUND_HALF_UP) |
| `fecha` | date (ISO) | ✅ | Fecha de captura |
| `operador` | str | ✅ | Quién relevó (email/ID) |
| `observaciones` | str | ❌ | Notas libres |
| `evidencias[]` | list[str] (URLs) | ❌ | Fotos (bucket Supabase Storage) |

## 3. Reglas de datos
1. Todo monto en `Decimal` + `ROUND_HALF_UP` (nunca `float`/`int` para dinero).
2. Cero invención: si falta dato, marcar `null`/`pendiente`, no asumir.
3. Idempotencia: upsert por `(almacen, comuna, fecha)`.
4. Validación Pydantic: `min_length`, `gt=0` para `precio_clp`.

## 4. Flujo de captura en terreno
1. Capturar en móvil/CLI → validar esquema local.
2. Persistir en Supabase (tabla propia).
3. Calcular resumen en servidor (`total_relevamientos`, `promedio_precio_clp`).
4. Handoff al Profesor Tierra (recálculo/cotización) y al CEO Informático (auditoría).
5. Registrar incidencias en `BUGS.md` (ID correlativo `BUG-XXX`).

## 5. Integración
- **Supabase:** tabla `obrero_almacenes_relevamiento` + RLS.
- **API:** `POST /api/v1/obrero/almacenes` protegido con `verify_api_key` + `enforce_rate_limit`.
- **Dashboard:** vista de lectura en `app/frontend/dashboard.py` (envío `X-API-Key`).
- **RAG:** opcional — inyectar resúmenes como chunks en `knowledge_chunks_v2` con `domain=tierra` vía pipeline.

## 6. Cierre
No se ejecuta `git push` sin orden explícita del CEO Informático.

---
_Plantilla ligera — DepaFix 3.0 · Elemento Tierra / Obrero Almacenes._
