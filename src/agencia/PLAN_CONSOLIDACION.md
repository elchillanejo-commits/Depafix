# Plan de consolidación — Agencia IKKI

Fecha: 2026-10-24 · Estado: **PROPUESTA, sin ejecutar**
Fuera de alcance (no se toca): `data/`, `.env`, Supabase.

---

## 1. Inventario de las 5 carpetas

### 1.1 `src/agencia/` — ACTIVO (código de producción)
El `Dockerfile` arranca `uvicorn src.agencia.api:app`; esta es la única carpeta que se despliega.

| Archivo | Tamaño | Git | Rol |
|---|---|---|---|
| api.py | 6.1K | modificado | FastAPI: `/agencia/ikki/simular` y otros |
| motor_ikki.py | 6.3K | modificado | Motor de copy/estrategia |
| motor_cda.py | 11.1K | **sin trackear** | Motor CDA (fee fijo + % pauta, embudos) |
| cda.py | 9.1K | **sin trackear** | Lógica CDA |
| esquemas.py | 9.0K | **sin trackear** | Modelos Pydantic |
| benchmarks.py | 3.2K | **sin trackear** | Benchmarks por rubro |
| repositorio_ikki.py | 7.5K | **sin trackear** | Persistencia en `campanas_ikki`, `presupuestos_ikki`, `leads_ikki` |
| dashboard.py | 13.7K | trackeado | Streamlit |
| meta_ads_integrator.py | 3.3K | trackeado | Meta Ads |
| prompt_engineer.py, prompts/ikki_system.txt | 1.6K / 0.4K | trackeado | System prompt |
| simulador_kimi.py | 2.0K | trackeado | Simulador |
| nutriente.py, auto_nutriente.py, local_brain.py, seed_knowledge.py, procesar_conocimiento.py | ~10K | trackeado | Ingesta de conocimiento (FAISS/SQLite en `data/`) |
| generar_propuesta.py, generar_reporte.py, generar_masivo.py | ~11.7K | trackeado | Generación de PDF/propuestas |
| \_\_init\_\_.py | 0 | trackeado | — |

21 archivos. Relacionado, fuera de la carpeta: `tests/test_ikki_api.py` (sin trackear).

### 1.2 `07_IKKI_MARKETING/` — NUEVO (sin trackear; artefactos de soporte, no código de la app)
| Archivo | Tamaño | Contenido |
|---|---|---|
| sql/06_agentes_marketing_ddl.sql | 9.6K | DDL `campanas_ikki`, `leads_ikki`, índices, trigger `ikki_set_updated_at` |
| sql/07_ikki_telemetria_gestalt.sql | 11.7K | ALTER de embudos B2C/B2B + UTM, tabla `presupuestos_ikki`, vista `vw_ikki_presupuesto_mensual` |
| smoke_test_ikki.py | 1.8K | Smoke test con TestClient sobre `src.agencia.api` (cliente Gestalt) |
| smoke_test_response.json | 13.1K | Salida generada por el smoke test |
| smoke_test_curl_response.json | 10.2K | Salida del curl manual |
| fuentes_videos/ | vacío | Placeholder |
| \_\_pycache\_\_/ | — | Basura |

`HILO_CONDUCTOR.txt` define `07_IKKI_MARKETING` como **carpeta del SQL Editor de Supabase** (convención `NN_DOMINIO`), no como paquete Python.

### 1.3 `ikki/` — LEGADO (vacío en disco)
Solo contiene `__pycache__/` con `campana.cpython-312.pyc`, `crear_afiche.cpython-312.pyc` y `__init__.cpython-312.pyc` (21 jul).
**No hay ningún `.py` en disco ni en la rama `main`.** El código fuente existe en git, en el commit `3588e98`
("generador de afiches Ikki + endpoints /api/generar_afiche y /api/campana/crear"), que está en las ramas
`master`, `origin/master` y `origin/feature/ikki-afiches`, **no en `main`**:
- `ikki/crear_afiche.py` (149 líneas): genera afiches con Pillow
- `ikki/campana.py` (115 líneas): sube a Supabase Storage (bucket `afiches`) y escribe en la tabla `campanas`

### 1.4 `marketing/` — casi vacío (trackeado)
| Archivo | Tamaño | Contenido |
|---|---|---|
| colegios.md | 0.8K | One-pager comercial "Depafix para Colegios Subvencionados" (SENCE, Ley 21.778) |
| colegios.pdf | 38K | PDF del mismo one-pager |

No es código de IKKI: es material comercial de venta.

### 1.5 `01_SERVIU_backup/marketing/` — LEGADO (ignorado por `.gitignore:58`, **no versionado**)
| Archivo | Tamaño | Contenido |
|---|---|---|
| ikki_engine.py | 2.7K | Ciclo IKKI: carga insights → system prompt → GPT-4o → `reportar_salud` |
| ikki_campaign_engine.py | 0.8K | `generar_anuncio_ikki()` (hook/cuerpo/CTA) con GPT-4o |
| run_ikki.py | 0.5K | CLI para `ikki_engine` |
| marketing_leads_connector.py | 0.6K | Upsert de leads en la tabla `clientes` |
| data/rolando_arellano_insights.json | 3.1K | **Principios de marketing de Rolando Arellano adaptados al holding** |
| \_\_init\_\_.py | 0 | — |

Depende de `scripts.telemetria` y de imports relativos rotos (`from marketing_leads_connector import ...`); no corre tal como está.

---

## 2. Duplicados detectados

**No hay duplicados byte a byte** entre las 5 carpetas (lo comprobé con md5). Lo que sí hay son **solapamientos funcionales**:

| Función | Versión activa (`src/agencia/`) | Versión legada | Veredicto |
|---|---|---|---|
| Generar copy/anuncio IKKI | `motor_ikki.py` + `prompt_engineer.py` + `prompts/ikki_system.txt` | `01_SERVIU_backup/marketing/ikki_engine.py`, `ikki_campaign_engine.py` | La activa la reemplaza. La legada usa OpenAI GPT-4o directo |
| Registro de leads | `repositorio_ikki.py` → `leads_ikki` | `marketing_leads_connector.py` → `clientes` | Tablas distintas. La activa la reemplaza |
| Registro de campañas | `repositorio_ikki.py` → `campanas_ikki` | `ikki/campana.py` (git) → `campanas` + Storage | Tablas distintas. La activa no cubre afiches ni Storage |
| Tests del endpoint | `tests/test_ikki_api.py` | `07_IKKI_MARKETING/smoke_test_ikki.py` | Se solapan en parte: el smoke test es un script con asserts, no pytest |
| CLI de ejecución | — | `run_ikki.py` | Obsoleto |

---

## 3. Archivos únicos por carpeta (lo que solo existe ahí)

**src/agencia/**: todo su contenido es único: motor CDA, esquemas, repositorio, dashboard, ingesta de conocimiento y generadores de PDF.

**07_IKKI_MARKETING/**: único y valioso:
- `sql/06_*.sql` y `sql/07_*.sql`: **es el único DDL** de las tablas que usa `repositorio_ikki.py` (`campanas_ikki`, `leads_ikki`, `presupuestos_ikki`). Sin estos archivos, el código no tiene esquema versionado.
- `smoke_test_ikki.py`: prueba de humo con los números del caso Gestalt (fee 1.300.000, leads B2C 51 / B2B 14).
- `*_response.json`: salidas generadas. Se pueden regenerar.

**ikki/ (vía git)**: única la funcionalidad de **afiches** (Pillow + Supabase Storage). No existe en `src/agencia/`.

**marketing/**: único el one-pager de Colegios (material comercial).

**01_SERVIU_backup/marketing/**: único y **lo más valioso del legado**: `rolando_arellano_insights.json`. Corresponde directamente al Día 10 del GANTT ("Inyección del JSON al System_Prompt de Ikki"), y `src/agencia/` no tiene nada equivalente. La función `construir_system_prompt()` de `ikki_engine.py` ya implementa ese patrón.

---

## 4. ¿Qué vale la pena rescatar del legado?

| Prioridad | Qué | Desde | Por qué |
|---|---|---|---|
| **Alta** | `rolando_arellano_insights.json` | 01_SERVIU_backup/marketing/data/ | Conocimiento curado y sin versionar: se pierde si se borra el backup. Alimenta el Día 10 del GANTT |
| Media | Lógica de `construir_system_prompt()` (unas 8 líneas) | ikki_engine.py | Patrón para inyectar insights en `prompt_engineer.py`. Hay que reescribirla, no copiarla |
| Media | `crear_afiche.py` / `campana.py` | git `3588e98` (rama master) | Única capacidad de afiches. Rescatar solo si los afiches siguen en el roadmap |
| Baja | Estructura hook/cuerpo/CTA | ikki_campaign_engine.py | Se puede incorporar como instrucción en `prompts/ikki_system.txt` |
| Nula | run_ikki.py, marketing_leads_connector.py, \_\_init\_\_.py | — | Obsoletos y con imports rotos |

---

## 5. Plan propuesto

Estructura objetivo: **todo el código en `src/agencia/`**. `07_IKKI_MARKETING/` queda solo como espejo del SQL Editor (SQL versionado), según la convención de HILO_CONDUCTOR.

### 5.1 MOVER
| Origen | Destino | Nota |
|---|---|---|
| `01_SERVIU_backup/marketing/data/rolando_arellano_insights.json` | `src/agencia/conocimiento/rolando_arellano_insights.json` | Copiar y versionar en git. No usar `data/` (zona no tocable y con otro propósito) |
| `07_IKKI_MARKETING/smoke_test_ikki.py` | `tests/smoke_test_ikki.py` (o convertirlo en un caso de `tests/test_ikki_api.py`) | Hay que ajustar `PROJECT_ROOT` (`parents[1]` sigue siendo válido desde `tests/`) y la ruta de salida del JSON |
| `07_IKKI_MARKETING/sql/*.sql` | **Se quedan** en `07_IKKI_MARKETING/sql/` y se agregan a git | Es la convención del SQL Editor. Alternativa: `sql/07_ikki/` junto a `sql/alter_operaciones_add_sizing.sql` |
| `marketing/colegios.{md,pdf}` | `docs/comercial/colegios.{md,pdf}` (opcional) | Solo para liberar el nombre `marketing/`. Usar `git mv` |
| `ikki/crear_afiche.py`, `ikki/campana.py` | `src/agencia/afiches/` | **Solo si se decide rescatar afiches** (`git show 3588e98:ikki/crear_afiche.py > ...`). Hay que adaptarlos a `repositorio_ikki` y a la tabla `campanas_ikki` |

### 5.2 ARCHIVAR en `_ARCHIVE/2026-10-24_ikki_legado/`
(siguiendo el patrón existente `_ARCHIVE/2026-09-29/`, `_ARCHIVE/2026-10-09/`)
| Qué | Motivo |
|---|---|
| `01_SERVIU_backup/marketing/` completo (después de copiar el JSON) | Conservar la referencia de `ikki_engine.py` sin dejarlo en el árbol activo |
| `07_IKKI_MARKETING/smoke_test_curl_response.json` | Evidencia del smoke test del 23 oct. Se puede regenerar, pero sirve para auditar el Día 11 |

### 5.3 BORRAR
| Qué | Motivo |
|---|---|
| `ikki/` (solo tiene `__pycache__`) | Sin fuentes. El código vive en git (`3588e98`) |
| `07_IKKI_MARKETING/__pycache__/` | Basura de compilación |
| `07_IKKI_MARKETING/fuentes_videos/` (vacía) | Placeholder vacío. Recrearla cuando se haga el Día 8 |
| `07_IKKI_MARKETING/smoke_test_response.json` | Lo regenera el smoke test en cada corrida. Agregarlo a `.gitignore` |
| `marketing/` (si queda vacía después de mover colegios) | — |

### 5.4 Secuencia sugerida (cuando se apruebe)
1. Commit de seguridad del estado actual de `src/agencia/` + `tests/test_ikki_api.py` (hay 5 archivos clave sin trackear).
2. Copiar el JSON de Arellano → `src/agencia/conocimiento/` y hacer commit.
3. `git add 07_IKKI_MARKETING/sql/` y hacer commit.
4. Mover el smoke test a `tests/`, correr `pytest tests/` y el smoke test, y confirmar que pasan.
5. Archivar `01_SERVIU_backup/marketing/` → `_ARCHIVE/2026-10-24_ikki_legado/`.
6. Borrar `ikki/`, los `__pycache__` y `fuentes_videos/`.
7. (Opcional) Mover `marketing/colegios.*` → `docs/comercial/`.
8. (Decisión aparte) Rescatar afiches desde `3588e98`.

---

## 6. Riesgos

| Riesgo | Impacto | Mitigación |
|---|---|---|
| **5 archivos core sin trackear** (`motor_cda.py`, `cda.py`, `esquemas.py`, `benchmarks.py`, `repositorio_ikki.py`) y `api.py` importa varios de ellos | Si se pierden, el deploy (`Dockerfile`) se rompe | Paso 1: commit antes de mover cualquier cosa |
| `01_SERVIU_backup/` está en `.gitignore` | Si se borra o archiva mal, `rolando_arellano_insights.json` se pierde para siempre (no está en git) | Copiarlo y versionarlo **antes** de archivar. `_ARCHIVE/` **también está ignorado** (`.gitignore:38`): archivar no equivale a respaldar |
| Código de afiches solo en las ramas `master` / `feature/ikki-afiches` | Si se eliminan esas ramas, se pierde | No borrar esas ramas, o rescatar el código antes de hacerlo |
| Los SQL dicen "no ejecutar aún contra la nube" y no está claro si ya corrieron en Supabase | `repositorio_ikki.py` falla si faltan las tablas | Este plan no toca Supabase. Verificar el estado por separado |
| Bucket `afiches` y tabla `campanas` (legados) pueden seguir existiendo en Supabase | Datos huérfanos o confusión con `campanas_ikki` | Fuera de alcance. Anotarlo para una revisión de Supabase |
| `07_IKKI_MARKETING` tiene un doble significado (carpeta local y carpeta del SQL Editor) | Alguien puede volver a meter código Python ahí | Agregar un README de una línea: "solo SQL, el código vive en src/agencia/" |
| El smoke test escribe el JSON junto a sí mismo (`Path(__file__).with_name`) | Al moverlo a `tests/` ensucia `tests/` | Redirigir la salida a `tmp/` o ignorarla en git |
| Hay rutas hardcodeadas a `07_IKKI_MARKETING` en `HILO_CONDUCTOR.txt` y `ESTADO_LOCAL_IKKI.txt` | Solo documentación | Actualizarlas después de consolidar. No hay imports de código que apunten a carpetas legadas (verificado con grep) |
