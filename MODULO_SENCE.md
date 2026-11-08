# Módulo SENCE — DepaFix

Fecha de cierre: 3 de noviembre de 2026.
Estado: **API y tool de saldo operativas**. `coach_sence` y `franquicia_empresas` están desplegadas; `franquicia_empresas` tiene un registro de prueba con RUT ficticio `76.123.456-7` y aún no tiene el RUT real de Zengin (`77253931-2`); `otec_info` no está definida.

---

## 1. Descripción

El módulo SENCE cubre dos frentes:

1. **Saldo de franquicia tributaria SENCE** por RUT de empresa, vía tool determinista y API.
2. **Cotizador de cursos** a partir de un PDF de cotización de proveedor, con cálculo de totales y generación de presupuesto HTML.

| Componente | Archivo | Rol |
|---|---|---|
| API | `api_cotizador.py` | FastAPI: `/health`, `/calcular-franquicia`, `/cotizar`, `/api/materiales/{proyecto}` |
| Tool de saldo | `sence_tools.py` | `calcular_saldo_franquicia(rut_empresa, trabajadores)` |
| CEO / CLI | `mente_360.py` | Modo `--saldo-sence <RUT>` + RAG sobre `coach_sence` |
| Ingesta de conocimiento | `ingestar_sence.py` | Chunking, embeddings y carga a `coach_sence` |
| DDL | `sql/coach_sence.sql`, `sql/franquicia_empresas.sql` | Esquemas y RPC de búsqueda |
| Datos de ejemplo | `sql/franquicia_empresas_ejemplo.sql` | Registro de prueba (RUT ficticio `76.123.456-7`) |

### Fórmula

```text
masa_imponible    = suma de remuneraciones de los trabajadores
tope_anual        = 4.5 * UTM_VALOR
franquicia_anual  = min(masa_imponible * 0.06, tope_anual)
disponible        = max(franquicia_anual - usado, 0)
```

- El tope de **4,5 UTM es anual por empresa**, no por trabajador.
- Con `UTM_VALOR=67000`, el tope anual es **$301.500**.
- Si el RUT existe en `franquicia_empresas`, se usan `franquicia_anual`, `usado` y `disponible` de la tabla (`fuente="franquicia_empresas"`, `es_estimacion=false`).
- Si no existe, se calcula la estimación (`fuente="estimacion"`, `es_estimacion=true`).

---

## 2. Configuración

Variables relevantes en `.env`:

```env
UTM_VALOR=67000
SUPABASE_URL=https://<proyecto>.supabase.co
SUPABASE_SERVICE_ROLE_KEY=<service_role>
OPENCODE_API_KEY=<api_key>
```

`UTM_VALOR` ya está configurada en `.env` (línea 13) y es leída por `sence_tools.py`. Si falta o es inválida, la tool usa `67000` por defecto.

### Levantar la API

```bash
cd /home/ibar/DepaFix_Maestro
.venv/bin/python -m uvicorn api_cotizador:app --host 0.0.0.0 --port 8000
```

> Usar `.venv/bin/python`: el `python3` del sistema no tiene `langchain_openai` ni el resto de dependencias del proyecto.

---

## 3. Endpoints

### `GET /health`

```bash
curl -s http://localhost:8000/health
```

```json
{"status":"ok"}
```

### `POST /calcular-franquicia`

Body:

```json
{
  "rut_empresa": "77253931-2",
  "trabajadores": [
    {"remuneracion": 1000000},
    {"remuneracion": 1500000}
  ]
}
```

#### Caso A — RUT Zengin (`77253931-2`)

```bash
curl -s -X POST http://localhost:8000/calcular-franquicia \
  -H "Content-Type: application/json" \
  -d '{"rut_empresa":"77253931-2","trabajadores":[{"remuneracion":1000000},{"remuneracion":1500000}]}'
```

Respuesta verificada el 2026-11-03 (sin registro en `franquicia_empresas`):

```json
{
  "success": true,
  "data": {
    "rut_empresa": "77253931-2",
    "rut": "77253931-2",
    "razon_social": "Desconocida",
    "trabajadores": 2,
    "masa_imponible": 2500000.0,
    "utm_valor": 67000.0,
    "tope_anual": 301500.0,
    "franquicia_anual": 150000.0,
    "usado": 0.0,
    "disponible": 150000.0,
    "año": 2026,
    "fuente": "estimacion",
    "es_estimacion": true,
    "nota": "No hay registro en franquicia_empresas para este RUT; se entrega una estimación con 6% de la masa imponible y tope anual de 4,5 UTM por empresa."
  }
}
```

#### Caso B — RUT sin registro (`11111111-1`)

```bash
curl -s -X POST http://localhost:8000/calcular-franquicia \
  -H "Content-Type: application/json" \
  -d '{"rut_empresa":"11111111-1","trabajadores":[{"remuneracion":800000}]}'
```

Respuesta: `franquicia_anual=48000`, `disponible=48000`, `es_estimacion=true`.

#### Caso C — RUT con registro oficial (seed actual: `76.123.456-7`)

La tabla desplegada tiene un registro de prueba con RUT ficticio `76.123.456-7`. La respuesta usa los valores de la tabla:

```bash
curl -s -X POST http://localhost:8000/calcular-franquicia \
  -H "Content-Type: application/json" \
  -d '{"rut_empresa":"76.123.456-7","trabajadores":[]}'
```

```json
{
  "success": true,
  "data": {
    "rut_empresa": "76.123.456-7",
    "razon_social": "Zengin OTEC SpA",
    "franquicia_anual": 301500.0,
    "usado": 50000.0,
    "disponible": 251500.0,
    "año": 2026,
    "fuente": "franquicia_empresas",
    "es_estimacion": false
  }
}
```

> El RUT real de Zengin (`77253931-2`) todavía no tiene fila; para ese RUT la API responde estimación. El registro de prueba no debe usarse como dato financiero real.

### `POST /cotizar`

Genera un presupuesto HTML a partir de un PDF de cotización de proveedor. Campos multipart:

| Campo | Tipo | Ejemplo |
|---|---|---|
| `pdf` | archivo PDF | `cotizacion.pdf` |
| `proyecto` | texto | `PRY-BLANCO-1313` |
| `proveedor` | texto | `AMD` |
| `sku_prefix` | texto | `AMD` |
| `fecha_requerida` | `YYYY-MM-DD` | `2026-11-15` |

```bash
curl -s -X POST http://localhost:8000/cotizar \
  -F "pdf=@cotizacion.pdf" \
  -F "proyecto=PRY-BLANCO-1313" \
  -F "proveedor=AMD" \
  -F "sku_prefix=AMD" \
  -F "fecha_requerida=2026-11-15"
```

Respuesta:

```json
{
  "success": true,
  "total_cliente": 2303090,
  "total_iva": 367720,
  "ruta_html": "/home/ibar/DepaFix_Maestro/output/presupuesto_PRY-BLANCO-1313.html"
}
```

> Los totales son de referencia del presupuesto corregido `PRY-BLANCO-1313`; el endpoint recalcula según el PDF recibido y sobrescribe el HTML de salida. El PDF se elimina al finalizar.

---

## 4. Tablas en Supabase

### Estado de despliegue (verificado 2026-11-03)

| Tabla | Estado | Uso |
|---|---|---|
| `coach_sence` | ✅ Desplegada y accesible | RAG del CEO vía `match_coach_sence` |
| `franquicia_empresas` | ✅ Desplegada con 1 registro de prueba (RUT ficticio `76.123.456-7`) | Saldo oficial por RUT; falta cargar el RUT real `77253931-2` |
| `otec_info` | ❌ No definida ni desplegada | Datos maestros de la OTEC (pendiente) |

### `coach_sence`

DDL: `sql/coach_sence.sql`.

| Columna | Tipo | Notas |
|---|---|---|
| `id` | `bigint` | Identity, PK |
| `contenido` | `text` | Chunk de texto |
| `metadata` | `jsonb` | Default `'{}'` |
| `embedding` | `vector(384)` | Embedding del chunk |
| `hash_origen` | `text` | Único (índice) |
| `created_at` | `timestamptz` | Default `now()` |

Índices: HNSW sobre `embedding` (`vector_cosine_ops`), único sobre `hash_origen`, e índice sobre `metadata->>'tipo'`.

RPC:

```sql
match_coach_sence(query_embedding vector(384), match_threshold float, match_count int, p_tipo text)
```

Devuelve `id`, `contenido`, `metadata`, `similarity`.

Metadata que escribe `ingestar_sence.py`:

```json
{
  "tema": "sence",
  "tipo": "curso|franquicia|normativa|...",
  "archivo": "nombre.pdf",
  "ruta": "/ruta/completa.pdf",
  "fuente": "zengin|os10"
}
```

### `franquicia_empresas`

DDL canónico: `sql/franquicia_empresas.sql`. La tabla está desplegada y accesible (verificado 2026-11-03).

| Columna | Tipo | Notas |
|---|---|---|
| `id` | `bigint` | Identity, PK |
| `rut_empresa` | `text` | `NOT NULL UNIQUE` |
| `razon_social` | `text` | |
| `franquicia_anual` | `numeric(14,2)` | Default `0` |
| `usado` | `numeric(14,2)` | Default `0` |
| `disponible` | `numeric(14,2)` | Generated: `greatest(franquicia_anual - usado, 0)` |
| `año` | `integer` | Default año actual |
| `updated_at` | `timestamptz` | Trigger `set_updated_at_franquicia` |

> **Discrepancia detectada:** la tabla desplegada **no tiene** la columna generada `disponible`; la tool calcula `max(franquicia_anual - usado, 0)`. El DDL canónico sí la incluye. Para materializarla:
>
> ```sql
> alter table public.franquicia_empresas
> add column if not exists disponible numeric(14,2)
> generated always as (greatest(franquicia_anual - usado, 0)) stored;
> ```

Registro de prueba actual:

| `rut_empresa` | `razon_social` | `franquicia_anual` | `usado` | `disponible` calculado |
|---|---|---|---|---|
| `76.123.456-7` | Zengin OTEC SpA | 301500 | 50000 | 251500 |

> El RUT `76.123.456-7` es ficticio y proviene de `sql/franquicia_empresas_ejemplo.sql`. El RUT real de Zengin es `77253931-2` y **todavía no tiene fila**.

Para cargar el registro real de Zengin, reemplazar los placeholders por los montos reales:

```sql
insert into public.franquicia_empresas (
  rut_empresa, razon_social, franquicia_anual, usado, "año"
)
values (
  '77253931-2', 'Zengin Limitada',
  <<franquicia_anual_real>>, <<usado_real>>, 2026
)
on conflict (rut_empresa) do update set
  razon_social = excluded.razon_social,
  franquicia_anual = excluded.franquicia_anual,
  usado = excluded.usado,
  "año" = excluded."año",
  updated_at = now();
```

Mientras el RUT no tenga fila, la tool responde con estimación y `es_estimacion=true`.

### `otec_info`

Al 2026-11-03 **no existe DDL en el repositorio ni tabla visible en Supabase**, y no hay referencias en el código. No debe documentarse como operativa hasta definirla.

Propuesta de esquema mínimo (a validar antes de implementar):

| Columna | Tipo | Notas |
|---|---|---|
| `id` | `bigint` | Identity, PK |
| `rut_otec` | `text` | Único |
| `razon_social` | `text` | |
| `codigo_sence` | `text` | Código de OTEC |
| `region` | `text` | |
| `estado_acreditacion` | `text` | Vigente / vencida / en trámite |
| `contacto` | `jsonb` | Email, teléfono, dirección |
| `created_at` | `timestamptz` | Default `now()` |
| `updated_at` | `timestamptz` | Trigger de actualización |

---

## 5. Prueba del CEO con el RUT de Zengin

Comando exacto (modo tool determinista):

```bash
cd /home/ibar/DepaFix_Maestro
.venv/bin/python mente_360.py --saldo-sence 77253931-2
```

Salida verificada el 2026-11-03:

```json
{
  "rut": "77253931-2",
  "saldo_disponible": 0.0,
  "remanente": 0.0,
  "vigencia": 2026,
  "fuente": "estimacion",
  "franquicia_anual": 0.0,
  "usado": 0.0,
  "es_estimacion": true,
  "nota": "No hay registro en franquicia_empresas para este RUT; se entrega una estimación con 6% de la masa imponible y tope anual de 4,5 UTM por empresa.",
  "contexto_recuperado": [
    "R.U.T.:77.253.931- 2\nZENGIN LIMITADA\nGiro: SERVICIOS DE CAPACITACIÓN ..."
  ]
}
```

El RUT se confirma en el contexto recuperado de `coach_sence`. El saldo es `0` porque el comando no recibe remuneraciones y `franquicia_empresas` no tiene una fila para `77253931-2`. Para verificar el camino de tabla con el registro de prueba actual:

```bash
.venv/bin/python mente_360.py --saldo-sence 76.123.456-7
```

Salida verificada:

```json
{
  "rut": "76.123.456-7",
  "saldo_disponible": 251500.0,
  "remanente": 251500.0,
  "vigencia": 2026,
  "fuente": "franquicia_empresas",
  "franquicia_anual": 301500.0,
  "usado": 50000.0,
  "es_estimacion": false,
  "nota": "Registro oficial encontrado en franquicia_empresas."
}
```

Para obtener un monto para el RUT real de Zengin:

1. Cargar la masa salarial vía API:

```bash
curl -s -X POST http://localhost:8000/calcular-franquicia \
  -H "Content-Type: application/json" \
  -d '{"rut_empresa":"77253931-2","trabajadores":[{"remuneracion":1000000},{"remuneracion":1500000}]}'
```

2. O cargar la fila real de Zengin (`77253931-2`) en `franquicia_empresas` con datos financieros reales.

### Alternativa conversacional

```bash
.venv/bin/python agente_ceo_final.py "¿Cuál es el saldo de franquicia SENCE de Zengin Limitada, RUT 77253931-2?"
```

> `agente_ceo_final.py` enruta consultas SENCE, pero el comando determinista es `mente_360.py --saldo-sence`; el pipeline conversacional de `agente_ceo_final.py` todavía no invoca la tool de saldo.

---

## 6. Cierre y pendientes

Correcciones aplicadas a `sence_tools.py`:

- Lee `UTM_VALOR` desde `.env` (default `67000`).
- Acepta `trabajadores` como lista de dicts (`{"remuneracion": ...}`) y mantiene compatibilidad con `int`.
- Aplica el tope anual **por empresa** (`4.5 * UTM`), no por trabajador.
- Devuelve las claves que consumen la API y `mente_360.py` (`disponible`, `año`, `fuente`, `franquicia_anual`, `usado`, `es_estimacion`, `nota`).
- Cliente Supabase lazy: si faltan credenciales o la tabla no existe, cae a estimación sin romper la API.

Verificado:

- Tool directa con lista de dicts.
- `POST /calcular-franquicia` → HTTP 200 para RUT con registro (`76.123.456-7`) y sin registro (`77253931-2`).
- `mente_360.py --saldo-sence 77253931-2` → ejecuta y recupera contexto de Zengin (estimación).
- `mente_360.py --saldo-sence 76.123.456-7` → lee el registro de prueba y devuelve `disponible=251500`.

Pendiente para cierre completo:

1. Cargar el registro real de Zengin (`77253931-2`) en `franquicia_empresas` con datos financieros reales (la tabla ya está desplegada).
2. Agregar la columna generada `disponible` a la tabla desplegada (opcional; la tool ya la calcula).
3. Definir e implementar `otec_info`.
4. Opcional: integrar `calcular_saldo_franquicia` en el pipeline conversacional de `agente_ceo_final.py`.
