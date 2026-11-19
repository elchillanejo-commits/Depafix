# 🛠️ SKILL OBRERO — PLANTILLA BASE (DepaFix 3.0)

**Rol:** Obrero de Terreno — Captura de datos operativos en obra/almacén.
**Elemento padre:** Tierra (Construcción / SERVIU / Terreno) — coordinado por el CEO Informático & CTO Integral.
**Consumidores downstream:** Profesores (Tierra/Metal) y CEO Informático (Mente 360).

---

## 1. Identidad y alcance
- **Nombre sugerido:** `obrero-inteligencia-almacenes` (u oficio equivalente: `obrero-relevamiento-obra`, `obrero-inventario-materiales`).
- **Propósito:** Capturar, en terreno, datos estructurados (inventario, mediciones, incidencias, fotos, costos) y alimentar al Profesor Tierra y al CEO Informático sin mezclar lógicas con otros elementos (Agua/Aire/Metal/SENCE).
- **Aislamiento:** Solo lectura/escritura sobre su propia tabla/colección; nunca toca `cotizaciones`, `franquicia_empresas` ni `knowledge_chunks_v2` directamente.

## 2. Entradas (input contract)
| Campo | Tipo | Requerido | Descripción |
|---|---|---|---|
| `obra_id` | UUID/str | ✅ | Identificador de la obra/propiedad (FK a `propiedades_v1`/`inspecciones_terreno`). |
| `oficio` | str | ✅ | Oficio ejecutante (ej. `almacenes`, `pintura`, `electricidad`). |
| `ubicacion` | str | ✅ | Dirección/comuna en terreno. |
| `fecha` | date (ISO) | ✅ | Fecha de captura. |
| `items[]` | list[dict] | ✅ | Lista de ítems relevados (ver esquema abajo). |
| `observaciones` | str | ❌ | Notas libres del obrero. |
| `evidencias[]` | list[str] (URLs) | ❌ | Fotos/evidencias (bucket Supabase Storage). |
| `operador` | str | ✅ | Quién capturó (email/ID). |

### Esquema de `items[]`
```json
{
  "codigo": "SKU o código interno",
  "descripcion": "Descripción del ítem",
  "unidad": "un | m² | m³ | gl | kg",
  "cantidad": 0.0,
  "costo_unitario_clp": 0.0,
  "estado": "ok | faltante | dañado | por_reponer",
  "ubicacion_fisica": "zona/estante (opcional)"
}
```

## 3. Salidas (output contract)
- **Registro persistido** en tabla destino (ej. `obrero_relevamiento_almacenes` o `inspecciones_terreno` extendida) con `id`, `created_at`, `payload_json`.
- **Resumen calculado** (en servidor, con `Decimal` + `ROUND_HALF_UP`):
  - `total_items`, `total_costo_clp`, `faltantes`, `dañados`.
- **Handoff al Profesor Tierra:** payload normalizado para recálculo/cotización.
- **Handoff al CEO Informático:** evento de auditoría (qué, quién, cuándo, dónde).

## 4. Reglas de gobernanza (inquebrantables)
1. **Precisión financiera:** Todo monto en `Decimal` + `ROUND_HALF_UP`. Nunca `float`/`int` para dinero.
2. **Cero invención:** No inventar códigos, precios ni cantidades; si falta dato, marcar `null`/`pendiente`, no asumir.
3. **Aislamiento de entornos:** Backend/CLI en `.venv`; dashboard en `.venv-dashboard`. No mezclar dependencias.
4. **Seguridad:** Sin credenciales hardcodeadas; claves por env; endpoints protegidos con `X-API-Key` + rate limit.
5. **Solo lectura en Supabase para auditoría:** no borrar/duplicar chunks ni registros de otros elementos.
6. **Idempotencia:** Re-ejecutar el mismo relevamiento no debe duplicar filas (upsert por `(obra_id, oficio, fecha)`).

## 5. Flujo operativo (checklist)
1. Capturar en terreno (móvil o CLI).
2. Validar esquema local (tipos, requeridos).
3. Persistir en Supabase (tabla destino).
4. Calcular resumen en servidor.
5. Notificar al Profesor Tierra (recálculo/cotización) y al CEO Informático (auditoría).
6. Registrar en `BUGS.md` cualquier incidencia (ID correlativo `BUG-XXX`).

## 6. Integración con el ecosistema
- **Supabase:** tabla propia + RLS por `operador`/`obra_id`. Storage bucket para evidencias.
- **API:** endpoint `POST /api/v1/obrero/relevamiento` protegido con `verify_api_key` + `enforce_rate_limit`.
- **Dashboard:** vista de lectura en `app/frontend/dashboard.py` (envío `X-API-Key`).
- **RAG:** opcional — inyectar resúmenes como chunks en `knowledge_chunks_v2` con `domain=tierra`.

## 7. Plantilla de implementación (checklist técnico)
- [ ] Crear tabla SQL (DDL en `sql/obrero_<oficio>.sql`).
- [ ] Crear router en `app/routers/obrero_<oficio>.py` y montarlo en `app/main.py` con `_public_dependencies`.
- [ ] Validar con Pydantic (alias, min_length, gt=0).
- [ ] Implementar upsert idempotente.
- [ ] `compileall` OK.
- [ ] Smoke test: POST válido → 201, POST sin key → 401, código inválido → 422.
- [ ] Documentar en `BUGS.md` si se detecta incidencia.

## 8. Ejemplo de uso (relevamiento de almacenes)
```bash
# CLI (futuro)
python3 obrero_almacenes.py --obra-id <UUID> --oficio almacenes --fecha 2026-11-19 --archivo items.json
# API
curl -X POST https://.../api/v1/obrero/relevamiento \
  -H "X-API-Key: $DEPAFIX_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"obra_id":"...","oficio":"almacenes","ubicacion":"...","fecha":"2026-11-19","items":[...],"operador":"..."}'
```

## 9. Cierre
Toda incidencia se registra en `BUGS.md` con ID correlativo. No se ejecuta `git push` sin orden explícita del CEO Informático.

---
_Plantilla base — DepaFix 3.0 · Elemento Tierra / Obrero de Terreno._
