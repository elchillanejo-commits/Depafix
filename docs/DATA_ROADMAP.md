# DepaFix — Data Roadmap (Cotizador de Pinturas)

**Proyecto:** `~/DepaFix_Maestro`
**Entorno:** Supabase (proyecto `gylyzcjkswltwpouktbi`)
**Última auditoría:** 2026-11-07
**Última actualización (deuda técnica):** 2026-11-07
**Responsable:** Ingeniero de Datos (scrapers Playwright / cotizador Supabase)

---

## 1. Tablas relevantes para el cotizador

Todas en el esquema `public`.

### `productos`
Catálogo de productos scraped (Sodimac). Es la tabla maestra que consulta el
motor de cotización (`src/data/cotizador.py`, función `_buscar_producto`).

| Columna | Tipo | Nulo | Comentario |
|---|---|---|---|
| `id` | uuid | NO | PK |
| `retailer_id` | uuid | NO | FK → `retailers.id` |
| `sku` | text | SÍ | Código del producto. Debe ser único por retailer. |
| `descripcion` | text | SÍ | Nombre del producto. |
| `unidad` | text | SÍ | Ej. "Galón", "unidad". Frecuentemente NULL (ver riesgos). |
| `categoria` | text | SÍ | Ej. "Pintura", "Cemento". Frecuentemente NULL (ver riesgos). |
| `created_at` | timestamptz | SÍ | Fecha de inserción. No existe `updated_at`. |

**Restricción:** `UNIQUE (sku, retailer_id)` definida en `sql/14_add_unique_constraint.sql` (2026-11-07, idempotente) — **pendiente de ejecutar en Supabase**. El scraper (`scraper_sodimac.py`, `asegurar_producto`) además consulta/inserta por la dupla `(sku, retailer_id)`.

### `precios_historial`
Histórico de precios por producto. Es la fuente de precio del cotizador
(`obtener_ultimo_precio` toma el registro más reciente por `producto_id`).

| Columna | Tipo | Nulo | Comentario |
|---|---|---|---|
| `id` | bigint | NO | PK (identity) |
| `producto_id` | uuid | NO | FK → `productos.id` |
| `precio_neto` | numeric | SÍ | Precio neto (CLP). Origen: scraper o derivado `lista/1.19`. **Debe ser > 0** para cotizar. |
| `precio_lista` | numeric | SÍ | Precio lista con IVA incluido (CLP). |
| `url_producto` | text | SÍ | URL de origen del scrapeo. |
| `fecha_scrapeo` | timestamptz | SÍ | Fecha del registro. No existe `created_at`. |
| `es_valido` | boolean | NO (default true) | Flag de validez. `false` = precio inválido/basura (conservado para auditoría). |

**Nota:** `scripts/fix_precios_invalidos.sql` agrega/mantiene `es_valido` y marca
inválidos sin borrarlos. El motor **ya filtra** `es_valido=true` y `precio_neto>0`
en `src/data/cotizador.py::obtener_ultimo_precio` (2026-11-07).

### `retailers`
| Columna | Tipo | Comentario |
|---|---|---|
| `id` | uuid | PK |
| `nombre` | text | Ej. "Sodimac" |
| `url_base` | text | Ej. "https://www.sodimac.cl/" |
| `created_at` | timestamptz | |

### `proyecto_materiales`
Usada por la API (`api_cotizador.py`, endpoint `/api/materiales`) y por
presupuestos de obra. No es la fuente de precio del cotizador de pinturas, pero
es parte del módulo de cotización general.

| Columna | Comentario |
|---|---|
| `margen_aplicado_pct` | numérico. **Unificado a 30.0 %** (2026-11-07; 6 filas alineadas). |
| `precio_unitario_real_clp` / `precio_unitario_cliente_clp` | costos y precios de cliente (cliente recalculado con 30 %). `costo_real_total_clp`/`total_cliente_clp` son generadas. |
| `estado_compra` | Ej. "pendiente". |

### Otras tablas del proyecto (no críticas para el cotizador de pinturas)
`coach_*`, `coach_pitches`, `coach_python`, `coach_shopify`, `coach_tierra`,
`coach_metal`, `materiales_catalogo`, `partida_receta`, `partida_receta_detalle`
(sql/dinamicos_precios.sql) — catálogo de materiales de obra general.

---

## 2. Reglas de negocio del cotizador

### Fuente de la verdad
El código fuente del motor está en `src/data/cotizador.py` (constantes en
líneas 27-31) y el PDF en `src/data/pdf_generator.py`.

### Constantes
```
RENDIMIENTO_M2_POR_GALON = 15.0   # m2 cubiertos por 1 galón (2 manos)
DESPERDICIO              = 0.10   # 10 % de desperdicio
MARGEN                   = 0.30   # 30 % de margen sobre el precio de venta neto
IVA                      = 0.19   # 19 % IVA (Chile)
MONEDA                   = "CLP"
```

### Fórmula de cálculo (por partida/SKU)
1. `galones_teoricos     = superficie_m2 / 15`
2. `galones_con_desperdicio = galones_teoricos * 1.10`
3. `galones_a_comprar    = ceil(galones_con_desperdicio)`  (redondeo hacia arriba, entero)
4. `costo_directo        = round(galones_a_comprar * precio_neto_unitario, 2)`
5. `precio_venta_neto    = round(costo_directo / (1 - 0.30), 2)`   ← margen 30 % sobre venta
6. `iva                  = round(precio_venta_neto * 0.19, 2)`
7. `precio_venta_con_iva = round(precio_venta_neto + iva, 2)`
8. `utilidad             = round(precio_venta_neto - costo_directo, 2)`

### Derivación de precio_neto desde precio_lista
En `obtener_ultimo_precio`:
```
precio_neto = round(precio_lista / (1 + IVA))   # round(lista / 1.19)
```
El scraper (`guardar_precio`) hace lo mismo: `round(lista / 1.19)`. Coherente.

### Resumen financiero
- `costo_directo_neto_total`
- `precio_venta_neto_total`
- `iva_total`
- `precio_venta_con_iva_total` (TOTAL al cliente)
- `utilidad_neta_total`
- `margen_utilidad_pct` = 30 %

---

## 3. Riesgos identificados y acciones (estado post-auditoría + deuda técnica)

| # | Riesgo | Estado | Detalle / Acción |
|---|---|---|---|
| R1 | SKU duplicados | ✅ **RESUELTO (código/SQL)** (2026-11-07) | 0 duplicados hoy. Restricción `UNIQUE (sku, retailer_id)` definida en `sql/14_add_unique_constraint.sql` (idempotente) — **ejecutar en Supabase** (ver §4). `asegurar_producto` ya consulta por `(sku, retailer_id)`. |
| R2 | Precio neto = 0 / NULL | ✅ **RESUELTO** (2026-11-07) | `cotizador.py::obtener_ultimo_precio` filtra `.eq("es_valido", True).gt("precio_neto", 0)`. `precios_historial.es_valido`. Script: `scripts/fix_precios_invalidos.sql`. |
| R3 | Precio bajo / servicio o no-construcción colado (ej. plancha vapor Xiaomi) | ✅ **RESUELTO (código)** (2026-11-07) | `scraper_sodimac.py`: filtro de **categorías válidas solo construcción** (cemento, fierro, madera, pintura, yeso, tabiquería, etc.) + exclusiones (electrodomésticos/tecnología/Xiaomi/plancha vapor/…); `candidato_valido` usa `PRECIO_MINIMO_REAL` y `resultado_es_valido` aplica el mismo filtro. Registro id=7 eliminado. |
| R4 | Datos incompletos en productos | ⚠️ Abierto | Varios `unidad/categoria` NULL. Bajo impacto; rellenar en próximos scrapes. |
| R5 | Falta de `created_at`/`updated_at` | ℹ️ Mitigado | Usar `created_at` (productos) y `fecha_scrapeo`/`id` (precios_historial). |
| R6 | Inconsistencia de margen (35% vs 30%) | ✅ **RESUELTO** (2026-11-07) | Unificado a **30 %** (Gemini). `cotizador.py` MARGEN=0.30; `proyecto_materiales` 6 filas alineadas. |

**Estado general:** 🟢 Verde. R1/R2/R3/R6 resueltos a nivel código/SQL/datos (R1 requiere ejecutar `sql/14_add_unique_constraint.sql` en Supabase). Pendientes vigentes: metadatos NULL (R4), **Evolution API ⏸️ pausada**, Fase 2 (scraping masivo/diario + PDF multipartida).

---

## 4. Scripts de corrección / DDL (guardados)

- `scripts/fix_sku_duplicados.sql` — elimina SKU duplicados dejando el más reciente (`created_at` DESC, `id` DESC). Idempotente.
- `scripts/fix_precios_invalidos.sql` — agrega `es_valido` y marca como inválidos los `precio_neto IS NULL OR = 0` **sin borrar** (enfoque seguro). El cotizador ya filtra `es_valido=true`.
- `sql/14_add_unique_constraint.sql` — **RESUELTO (definido, 2026-11-07)**: agrega `UNIQUE (sku, retailer_id)` en `public.productos` (idempotente). Ejecutar tras limpiar duplicados (hoy 0). Ver comando en nota de despliegue abajo.

> Despliegue SQL en Supabase: si no tienes DB connection string, usa **SQL Editor → New query → pegar contenido → Run**. Si tienes la connection string (Project Settings → Database): `psql "<DB_CONNECTION_STRING>" -v ON_ERROR_STOP=1 -f <archivo.sql>`.

---

## 5. Notas para agentes futuros

1. **Nunca confíes ciegamente en `precio_neto` de `precios_historial`**: el motor filtra `es_valido=true` y `precio_neto>0` (implementado 2026-11-07 en `obtener_ultimo_precio`); mantener este filtro en cualquier consulta de precios para cotización.
2. **SKU es la clave de unión**: el cotizador busca por `sku` en `productos` y luego el precio más reciente en `precios_historial` por `producto_id`. Si el scraper inserta un SKU duplicado, `.limit(1)` en `_buscar_producto` puede devolver el incorrecto.
3. **Margen fijo 30 % y IVA 19 %**: definido por Gemini. Hardcodeado en `src/data/cotizador.py` (`MARGEN=0.30`, `IVA=0.19`). `proyecto_materiales.margen_aplicado_pct` unificado a 30 % (2026-11-07). No cambiar sin actualizar `DATA_ROADMAP.md`, `pdf_generator.py` y datos en BD.
4. **Redondeo**: montos finales a 2 decimales con `round()`. `galones_a_comprar` usa `math.ceil` (hacia arriba, entero) — nunca redondear galones al abajo.
5. **Fuente de credenciales**: `.env` en la raíz (`SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`). El cotizador las lee con `dotenv` desde rutas candidatas (`repo/.env`, `~/DepaFix_Maestro/.env`, cwd).
6. **Antes de ejecutar scripts DDL en producción**, respaldar la base y ejecutar primero en un entorno de prueba.
7. **Después de cada corrida del scraper (`scraper_sodimac.py`)**, validar: duplicados de SKU y precios con `precio_neto <= 0` o `es_valido=false`. Ejecutar `scripts/fix_precios_invalidos.sql`/`scripts/fix_sku_duplicados.sql` según aplique.

## 6. Pendientes técnicos (vigentes, 2026-11-07)

| Pendiente | Estado | Responsable sugerido |
|---|---|---|
| Integración **Evolution API** (WhatsApp/automatización) | ⏸️ **PAUSADA** (pendiente) | `@build-data` / integración |
| Ejecutar `sql/14_add_unique_constraint.sql` en Supabase (restricción ya definida) | Pendiente de despliegue | `@build-data` / DBA |
| Completar `unidad/categoria` NULL en `productos` | Pendiente | `@build-data` |
| Fase 2 cotizador: scraping masivo/diario + PDF multipartida (agentes locales) | EN PROCESO | `@build-data`, `@build-docs` |

**Resueltos en esta ronda (2026-11-07):** filtro categorías válidas construcción + anti-servicios/precio mínimo en `scraper_sodimac.py` (evita colados tipo plancha vapor Xiaomi/id=7) y DDL `UNIQUE (sku, retailer_id)` en `sql/14_add_unique_constraint.sql`.
