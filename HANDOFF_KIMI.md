# HANDOFF — IKKI: RAG en producción + activar LLM

Fecha: 2026-10-25 · Repo: `/home/ibar/PROYECTOS/Proyectos/DepaFix` · Rama: `main` (sincronizada con `origin/main`)

---

## 1. Estado del deploy de hoy (verificado)

- `git push` hecho: `main` == `origin/main` (último commit `e40807e Feat: Motor IKKI conectado a RAG con pgvector`).
- API en Railway responde: `https://ikki-api-production.up.railway.app` → `/`, `/docs`, `/openapi.json` = 200.
  Endpoints: `POST /agencia/ikki/simular`, `POST /agencia/ikki/leads`, `POST /api/v1/simular`.
- `POST /agencia/ikki/simular` devuelve la simulación completa (fee, embudos, CDA, benchmarks,
  proyecciones, plan_30_dias, creatividades, cumplimiento, resumen, supuestos). Probado con `persistir=false`.
- Infra RAG lista:
  - Supabase: `knowledge_entries` (74 chunks padre, `fuente='video_txt'`) + `knowledge_chunks`
    (442 sub-fragmentos con `embedding vector(384)`) + RPC `match_knowledge(query_embedding, match_count, filtro_categoria)`.
    DDL: `07_IKKI_MARKETING/sql/09_pgvector_knowledge_chunks.sql`.
  - `src/agencia/rag.py` → `buscar()` / `obtener_contexto_relevante()` (pgvector, no FAISS).
  - `src/agencia/embeddings_onnx.py` → embedding de la pregunta con ONNX (sin torch), vectores idénticos a
    sentence-transformers. Modelo bajado en el build por `scripts/descargar_modelo_onnx.py` (revisión + sha256 fijos).
  - Imagen Docker: 1,71 GB (se excluyen `01_SERVIU_backup/`, `frontend/`, `models/`).

### ⚠️ Lo importante: la API todavía NO usa el RAG
- Las simulaciones de la API las hace **`MotorCDA`** (`src/agencia/motor_cda.py`), no `AgenciaIkkiMotor`.
- Las creatividades salen de **plantillas fijas** en `src/agencia/cda.py:141` → `creatividades(embudo)`.
  Ojo: para `rubro="inmobiliaria"` hoy devuelve textos de tests genéticos ("¿Test genético, examen o consulta?").
- La conexión RAG + LLM quedó hecha en `AgenciaIkkiMotor` (`src/agencia/motor_ikki.py`:
  `obtener_contexto_relevante()`, `generar_copys()`, usado por `simular_campana_completa()`), pero **ningún
  endpoint llama a `simular_campana_completa`**. La API solo usa `AgenciaIkkiMotor` para `obtener_caso_exito`.
  Quien sí la usa: `simulador_kimi.py` (y `dashboard.py` / `generar_propuesta.py` leen `copys_generados` de un JSON).

---

## 2. Activar el LLM en producción (Railway)

`generar_copys()` usa Anthropic solo si `IKKI_USE_MOCK=0` **y** hay `ANTHROPIC_API_KEY`; si no, o si el LLM
falla / no devuelve JSON, cae a copys fijos (`origen_copys="fijo"`). Modelo: `IKKI_LLM_MODEL` (default `claude-haiku-5-5`).

Desde `/home/ibar/PROYECTOS/Proyectos/DepaFix` (proyecto **`ikki-api`**, NO `Depafix`):

```bash
railway status                      # debe decir Project: ikki-api
railway variables --service ikki-api --environment production \
  --set "IKKI_USE_MOCK=0" \
  --set "ANTHROPIC_API_KEY=sk-ant-..." \
  --set "IKKI_LLM_MODEL=claude-haiku-5-5"
railway variables --service ikki-api --environment production   # confirmar (no pegar la key en chats)
```

Setear variables redepliega el servicio. Si no: `railway redeploy --service ikki-api` o
`railway up --service ikki-api --environment production`.
Alternativa sin CLI: Railway → proyecto ikki-api → servicio ikki-api → *Variables*.

**Esto por sí solo no cambia la respuesta de la API** (ver punto 3): primero hay que conectar `MotorCDA`.

---

## 3. Tarea pendiente: creatividades de la API con LLM + RAG

Objetivo: que `POST /agencia/ikki/simular` devuelva creatividades generadas por el LLM con contexto de `rag.py`.

1. Punto de enganche: `src/agencia/motor_cda.py:196`
   `creatividades=creatividades(distribucion.embudo)` (plantillas de `cda.py`).
2. Reutilizar lo ya hecho en `motor_ikki.py`: `AgenciaIkkiMotor.obtener_contexto_relevante(rubro)` y
   `generar_copys(rubro, cliente, contexto)` → devuelve `([{"titulo","cuerpo","cta"}], origen)`.
3. Adaptar al esquema `Creatividad` (`src/agencia/esquemas.py:181`), que además exige `formato`:
   mantener el `formato` de la plantilla y reemplazar `titulo/cuerpo/cta`.
4. **Fallback obligatorio** a las plantillas de `cda.py` si el RAG o el LLM fallan (la API no puede caerse).
5. Arreglar de paso que las plantillas no dependan del rubro (texto genético para inmobiliaria).
6. Una llamada al LLM por embudo (B2C/B2B), no por creatividad. Considerar caché por (rubro, embudo).
7. Agregar tests con el LLM y el RAG mockeados (ver punto 4); nunca llamar al LLM real en tests.
8. Cambios mínimos en `api.py` / `motor_ikki.py` (están en producción): pedir OK al usuario antes de tocar.
   **No tocar** `obtener_caso_exito` (solo casos `tipo='real'`).

Contrato: agregar campos está bien, no quitar ni renombrar los existentes de `SimulacionResponse`.

---

## 4. Advertencias técnicas

- **Railway:** desplegar SOLO en proyecto/servicio `ikki-api`. `Depafix` es otro proyecto; pisarlo es destructivo.
  `railway up` sube el directorio actual: correrlo desde la raíz del repo.
- **venv:** usar `venv/` (no `.venv/`). No borrarlo. Ojo: hoy fue recreado a las 12:10 por otra sesión y quedó
  **sin** `fastapi`, `onnxruntime`, etc. Reinstalar con `venv/bin/python -m pip install -r requirements.txt`
  (`venv/bin/pip` tiene el shebang roto: usar siempre `python -m pip`). Para ingesta local además:
  `sentence-transformers faiss-cpu`.
- **Probar como en producción (lo más fiable):**
  ```bash
  docker build -t ikki-test .
  docker run --rm --env-file .env --entrypoint python ikki-test -m src.agencia.rag "¿Cómo bajo el CPC en Google Ads?"
  # esperado: ids 38, 48, 43
  ```
  El build tarda ~10 min (descarga el modelo ONNX de 470 MB).
- **Tests:** `PYTHONPATH=. venv/bin/python -m pytest tests/test_ikki_api.py -q` (requiere el venv reinstalado).
  Simulación en prod sin escribir en la BD: `POST /agencia/ikki/simular` con `"persistir": false`.
- **Modelo RAG:** pregunta = `"query: "+texto`, pasajes = `"passage: "+texto` (ya lo hace `embeddings_onnx`).
  1ª consulta ~8 s (carga del modelo), siguientes ~300 ms → precargar en el startup si molesta.
- **Pricing:** "cuánto cobrar por Meta Ads" sin filtro no trae pricing; usar `categoria="Pricing_Agencia"`.
  Categorías: `Meta_Ads_Estructura`, `Google_Ads_CPC`, `Google_Ads_Estructura`, `Pricing_Agencia`, `Estrategia_General`.
- **Supabase:** `knowledge_chunks` tiene RLS sin políticas y `match_knowledge` solo es ejecutable por `service_role`.
  `SUPABASE_URL` / `SUPABASE_SERVICE_ROLE_KEY` en `.env` (local) y en Railway.
- **Re-ingesta:** `HF_HUB_OFFLINE=1 venv/bin/python src/agencia/ingestar_videos.py` (dry-run) → `--apply`.
  Regenera FAISS local y `knowledge_chunks`. Si cambias de modelo hay que regenerar todo y actualizar
  `embeddings_onnx.py` + `scripts/descargar_modelo_onnx.py`.
- **Pendiente del usuario:** SQL de limpieza (si no se corrió):
  `ALTER TABLE public.knowledge_entries DROP COLUMN IF EXISTS embedding;`
  Después `src/agencia/poblar_embeddings.py` queda obsoleto.
- Archivos sin seguimiento ajenos a este trabajo: `config/settings.yaml`, `structure.txt`, `data/nuevos_videos/`,
  `src/trading/rag_helper.py` (de otra sesión). No commitear sin preguntar.
