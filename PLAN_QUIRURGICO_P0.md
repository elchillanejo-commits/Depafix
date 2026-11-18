# 🛠️ PLAN DE EJECUCIÓN QUIRÚRGICA P0 — DEPAFIX 3.0
**Destino:** OpenCode CLI (Modo Build / Agente Ejecutor)  
**Repositorio:** `DepaFix_Maestro`  
**Stack:** Python 3.12, FastAPI (Railway), Supabase (`pgvector` + RLS), Streamlit (`.venv-dashboard`).  
**Regla de Oro:** Ajustes quirúrgicos. No romper endpoints operativos (`/health`, `POST /api/v1/cotizaciones/`). Registrar cualquier hallazgo crítico en `BUGS.md`.

---

## 🎯 CONTEXTO ACTUAL VERIFICADO
1. **Railway (`depafix-presupuestos-production.up.railway.app`):** Online en puerto 8080. `POST /api/v1/cotizaciones/` funciona (`201 Created`).
2. **Diagnóstico de Logs Recientes:**
   - `GET /api/v1/cotizaciones/` devuelve `405 Method Not Allowed` (falta el método GET en el router).
   - `POST /api/v1/rag/buscar` fallaba con `502 Bad Gateway` por error `42501: permission denied for function match_knowledge_v2` (se requiere validar permisos RPC o uso de `service_role` en backend).
   - Endpoints públicos (`cotizaciones`, `rag`, `presupuesto/csv`) carecen de autenticación por API Key y Rate Limiting.
   - Falta endpoint `/ready` de verificación profunda de dependencias (Supabase).

---

## 📋 TAREAS QUIRÚRGICAS PARA OPENCODE (EJECUTAR EN ORDEN)

### Tarea 1: Seguridad P0 (Auth + Rate Limit + CORS Configurable)
* **Objetivo:** Proteger los endpoints públicos sin bloquear el dashboard de Streamlit.
* **Acción en código:**
  1. Crear/actualizar dependencia de seguridad en `app/core/security.py` (o equivalente) que valide el header `X-API-Key` contra una variable de entorno `DEPAFIX_API_KEY` (si `DEPAFIX_API_KEY` no está definida en entorno local, permitir paso con warning en log para no romper desarrollo, pero exigirla si está configurada).
  2. Aplicar un Rate Limiter ligero en memoria (o `slowapi` si ya está en `requirements.txt`; no instalar librerías pesadas innecesarias) a `/api/v1/cotizaciones/`, `/api/v1/rag/buscar` y `/api/v1/presupuesto/csv`.
  3. Configurar `CORSMiddleware` en `app/main.py` leyendo `CORS_ORIGINS` desde `.env` (separado por comas, con fallback seguro a `http://localhost:8501,http://localhost:8502`).

### Tarea 2: Completar CRUD de Cotizaciones (`GET /api/v1/cotizaciones/`)
* **Objetivo:** Eliminar el error `405 Method Not Allowed` en el panel de Streamlit.
* **Acción en código:**
  1. En el router de cotizaciones (`app/routers/cotizaciones.py`), implementar `@router.get("/")` que consulte las últimas 50 cotizaciones ordenadas por `created_at` descendente desde Supabase.
  2. Verificar que el formato de respuesta sea consistente: `{"status": "success", "data": [...]}`.

### Tarea 3: Endpoint `/ready` (Deep Health Check)
* **Objetivo:** Diferenciar entre contenedor vivo (`/health`) y sistema listo con base de datos operativa (`/ready`).
* **Acción en código:**
  1. En `app/main.py` (o router de salud), crear `@app.get("/ready")`.
  2. Debe ejecutar una consulta mínima (`SELECT 1` o `.limit(1)` a la tabla `cotizaciones` o `knowledge` en Supabase) y responder `200 OK` con `{"status": "ready", "database": "connected"}` o `503 Service Unavailable` si falla la conexión o los permisos RLS.

### Tarea 4: Hardening de Credenciales y `.gitignore`
* **Objetivo:** Evitar fugas de secretos y contraseñas hardcodeadas.
* **Acción en código:**
  1. Auditar `app/` en busca de contraseñas o llaves escritas en texto plano (hardcoded) y moverlas a `os.getenv(...)`.
  2. Actualizar `.gitignore` para asegurar que ignore estrictamente: `.env`, `.env.*`, `*.venv*`, `.venv-dashboard/`, `__pycache__/`, `cookies.txt`, y archivos temporales de prueba.

### Tarea 5: Sincronizar Dashboard Streamlit (`app/frontend/dashboard.py`)
* **Objetivo:** Conectar el listado en vivo y enviar el header `X-API-Key` si existe en el entorno.
* **Acción en código:**
  1. Actualizar `app/frontend/dashboard.py` para enviar `headers={"X-API-Key": os.getenv("DEPAFIX_API_KEY", "")}` en todas las peticiones `requests.get` y `requests.post`.
  2. Restaurar la tabla dinámica (`st.dataframe`) en la columna "Historial en Supabase" ahora que `GET /api/v1/cotizaciones/` estará activo.

---

## ✅ CRITERIO DE ACEPTACIÓN (SMOKE TEST)
Al finalizar las modificaciones, OpenCode debe verificar localmente:
1. Que el servidor FastAPI levanta sin errores de sintaxis ni importación.
2. Que `pytest` o un script rápido de verificación comprueba `/health`, `/ready` y la estructura de los routers modificados.
3. Documentar cualquier cambio de variables de entorno requeridas en Railway (`DEPAFIX_API_KEY`, `CORS_ORIGINS`, `SUPABASE_KEY` con rol adecuado).
