# 00_ESTADO_PRODUCCION: Auditoría de Alineación Total

Generado 2026-07-16. Todo lo que sigue fue verificado en vivo (compilación
real de los 77 `.py` del repo, consultas reales a Supabase, `docker ps`,
`systemctl status`, `crontab -l`) -- no es una revisión solo de texto.

**Veredicto: el sistema NO está alineado todavía.** Hay 2 riesgos críticos
activos hoy mismo. Se corrigieron durante esta auditoría; quedan acciones
pendientes que requieren `sudo` o acceso a Supabase y se listan abajo.

## 1. Integridad del sistema -- checkpoints

| Checkpoint | Estado |
|---|---|
| `docs/01` a `docs/05` con nomenclatura y referencias cruzadas correctas | ✅ Corregido (ver #3) |
| Todo `core/`/`src/` usa `BASE_DIR`/`CORE_PATH`, sin rutas residuales | ✅ Corregido (`core/auditor_ia.py`, `src/trading/injector.py`) |
| `core/__init__.py` presente (paquete explícito, no namespace implícito) | ✅ Agregado |
| Los 77 `.py` del repo compilan sin `SyntaxError` | ✅ Corregido (ver riesgo #2) |
| `precios_serviu` / `reglas_contables` documentados = nombres reales en código | ✅ Corregido (ver #3) |
| Conectividad Supabase verificable con un comando | ✅ `tests/test_connectivity.py` |
| Exportador BI probado contra datos reales | ✅ `src/analytics/bi_exporter.py` -> `data/bi_export/presupuestos_bi.csv` |
| API FastAPI respondiendo | ✅ Docker, puerto 8001, `/health` -> `{"status":"ok","db":"connected"}` |
| RLS real = lo que documenta `04_POLITICAS_SEGURIDAD_RLS.md` | ❌ Pendiente -- rol `bi_readonly` no existe en la base real |
| Servicio systemd `depafix-api.service` operativo | ❌ Llevaba ~90 min en loop de fallo; plantilla corregida, falta reinstalar |
| Crontab apunta a archivos que existen | ❌ 31 de 34 tareas apuntan a rutas inexistentes |
| Sin credenciales en texto plano en el repo | ❌ Encontrado y corregido en el código; falta rotar la credencial real |

## 2. Riesgos detectados

### CRÍTICO -- credencial de Postgres expuesta en un repo público
Una contraseña de Postgres (no reproducida acá a propósito -- este archivo
mismo se commitea al repo público, citarla literal solo recrearía la fuga
en un archivo nuevo) estaba hardcodeada como valor por defecto en 17
archivos: `src/infrastructure/persistence/postgres_repository.py`,
`graphql_schema.py`, los 10 `cloud/*/main.py`, `skills/reporte_ejecutivo/generar_reporte.py`,
4 scripts en `scripts/`, y `docker-compose.yml` (2 líneas) -- commiteada
desde el primer commit. **El repo `elchillanejo-commits/Depafix` es público
en GitHub** -- confirmado vía API (`"private": false`). Además, la misma
contraseña está en texto plano en **8 líneas del crontab del sistema**
(fuera del repo).

Hecho ahora: removidos los defaults hardcodeados de los 17 archivos (ahora
exigen `PGPASSWORD`/`DB_PASS`/`POSTGRES_PASSWORD` por entorno, sin fallback).

Pendiente -- esto **no** lo puedo ejecutar yo, requiere decisión y acceso tuyo:
1. Rotar la contraseña real en Postgres/Supabase YA (la que está expuesta
   sigue siendo válida hasta que la cambies).
2. Limpiar el crontab (`crontab -e`) quitando la línea `PGPASSWORD=...`
   hardcodeada de las 8 líneas que la tienen.
3. La contraseña sigue en el historial de git aunque la borres del archivo
   actual -- si te importa, hay que reescribir historia (`git filter-repo`
   o BFG) y forzar push, lo cual reescribe commits para cualquiera que
   tenga el repo clonado. Avisame si querés que lo prepare; es destructivo
   y no lo hago sin tu confirmación explícita.

### CRÍTICO -- 10 microservicios cloud no arrancaban
`cloud/aquiles/main.py`, `cloud/aquiles/app/main.py` y sus equivalentes para
bilardo, siegfried, hermes y sancho tenían `\"\"\"` en vez de `"""` en el
docstring (línea 2 y 4) -- `SyntaxError` inmediato al importar. Ninguno de
los 5 servicios podía arrancar tal como estaba commiteado. **Corregido.**
Verificado: los 10 archivos compilan ahora (`py_compile`).

### ALTO -- `depafix-api.service` (systemd) en loop de fallo
`WorkingDirectory=core/` y `ExecStart=core/venv/bin/uvicorn` -- ni
`core/venv/` ni `core/main.py` existen (el venv y el `main.py` reales están
en la raíz del repo). `systemctl status` mostraba `failed (203/EXEC)`,
reiniciando cada pocos segundos desde hace ~90 min.

Corregido el archivo fuente `/home/ibar/depafix-api.service` (paths
apuntando a la raíz del repo). Para aplicarlo (requiere sudo, no lo corro yo):
```bash
sudo cp /home/ibar/depafix-api.service /etc/systemd/system/depafix-api.service
sudo systemctl daemon-reload
sudo systemctl restart depafix-api.service
sudo systemctl status depafix-api.service
```
Nota: la API ya está sirviendo en producción vía Docker en el puerto 8001
(`core-fastapi-1`, healthy) -- este systemd service en 8000 parece un
segundo camino de deploy que quedó desalineado, no el único punto de falla.

### ALTO -- crontab con rutas fantasma
31 de 34 tareas de cron apuntan a `core/agentes/*`, `core/scripts/*` o
`core/venv/*` -- ninguna de esas carpetas existe en este repo. Todo backup,
reporte, alerta de Telegram, scraping de materiales y monitoreo programado
por cron **lleva tiempo fallando en silencio** (o llenando de errores un log
que nadie revisa). Solo 3 tareas usan rutas reales:
`scripts/backup_cloud.sh`, `scripts/backup_diario.sh`, `scripts/deploy_total.sh`.
No toqué el crontab -- es estado vivo del sistema y limpiarlo/reescribirlo
es tu decisión. Revisalo con `crontab -e`.

### MEDIO -- RLS no sincronizado con lo documentado
Verificado en vivo con la key `anon`: `presupuestos`, `precios_serviu` y
`velas_cripto` son legibles públicamente hoy. `docs/02` y `docs/04`
documentan "solo lectura vía rol `bi_readonly`", pero ese rol no existe en
la base real. Comando de sincronización: `sql/create_bi_readonly.sql`
(actualizado en esta auditoría -- crea el rol, revoca el acceso de `anon`
y aplica la policy de solo-SELECT en las 3 tablas). Correr en el SQL Editor
de Supabase con permisos de owner.

### BAJO -- script en progreso con placeholder
`src/agents/centinela.py` (archivo nuevo, aparentemente en desarrollo)
tiene `"apikey": "tu_anon_key_aqui"` literal -- no funcional todavía, no es
una fuga real, pero no va a conectar hasta que se lea desde `.env`.

## 3. Cambios de código hechos en esta auditoría

- `core/auditor_ia.py`: `FALLBACK_JSONL` y el log de logging usaban rutas
  relativas al cwd; ahora usan `CORE_PATH` (mismo patrón que el resto).
- `src/trading/injector.py`: variable `root_dir` sin guardia -> renombrada
  a `CORE_PATH` con el guardia `if str(...) not in sys.path`, igual que
  `orquestador_cripto.py`/`data_pipeline.py`.
- `docs/02_MODELO_DATOS_SERVIU.md`: columnas corregidas para coincidir con
  `sql/create_precios_serviu.sql` real (`valor_unitario`/`created_at`, no
  `valor`/`fecha_actualizacion`; `id` es `SERIAL`, no `UUID`).
- `docs/03_LOGICA_NEGOCIO_CONTABLE.md`: nombra explícitamente `reglas_contables`
  (la tabla real que usa `core/auditor_ia.py`) y corrige la afirmación de
  que ese script usa `precios_serviu` (no la usa -- son subsistemas separados).
- `docs/04_POLITICAS_SEGURIDAD_RLS.md`: ahora lista las tablas cubiertas y
  el estado real de sincronización (no sincronizado, ver riesgo MEDIO).
- `docs/05_GUIA_CONEXION_POWERBI.md`: ahora cita explícitamente a
  `04_POLITICAS_SEGURIDAD_RLS.md` como fuente de verdad del acceso.
- `sql/create_bi_readonly.sql`: extendido para cubrir `precios_serviu` y
  `velas_cripto` además de `presupuestos`, con `REVOKE ALL ... FROM anon`
  explícito (el `ENABLE ROW LEVEL SECURITY` solo no alcanza si `anon` ya
  tiene un GRANT heredado).
- 16 archivos: password hardcodeada removida (ver riesgo CRÍTICO).
- 10 archivos `cloud/*/main.py`: `SyntaxError` corregido (ver riesgo CRÍTICO).
- `/home/ibar/depafix-api.service`: paths corregidos (ver riesgo ALTO).

## 4. Servicios activos (verificado, no asumido)

| Servicio | Estado real |
|---|---|
| Supabase (proyecto `gylyzcjkswltwpouktbi`) | ✅ Accesible, anon + service_role funcionando |
| Docker `core-fastapi-1` (puerto 8001) | ✅ `healthy`, `/health` responde `{"status":"ok","db":"connected"}` |
| Docker `core-postgres-1` | ✅ `healthy` |
| systemd `depafix-api.service` (puerto 8000) | ❌ Failed, corregido el origen, falta reinstalar (sudo) |
| Microservicios cloud (aquiles/bilardo/siegfried/hermes/sancho) | ⚠️ Código ya compila; ningún contenedor de `cloud/docker-compose.cloud.yml` está levantado actualmente |
| Cron (34 tareas) | ⚠️ Solo 3 apuntan a archivos existentes |
| Exportador BI (`src/analytics/bi_exporter.py`) | ✅ Probado end-to-end, exporta `presupuestos` a `data/bi_export/presupuestos_bi.csv` |
| RLS `bi_readonly` | ❌ No existe en la base real -- ver `sql/create_bi_readonly.sql` |
