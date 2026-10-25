# HANDOFF — Conectar `motor_ikki.py` al RAG (pgvector)

Fecha: 2026-10-25 · Contexto previo: Handoff 006 (ingesta de videos de Meta/Google Ads)

## Estado actual (hecho y verificado)

| Pieza | Dónde | Estado |
|---|---|---|
| Chunks padre (~700 palabras, 74 filas, `fuente='video_txt'`) | Supabase `knowledge_entries` | ✅ cargados |
| Sub-fragmentos (~150 palabras, 442 filas) + embedding 384d | Supabase `knowledge_chunks` | ✅ cargados |
| Búsqueda vectorial (mejor sub-fragmento por padre → devuelve padre) | Supabase RPC `match_knowledge(query_embedding, match_count, filtro_categoria)` | ✅ |
| DDL de lo anterior | `07_IKKI_MARKETING/sql/09_pgvector_knowledge_chunks.sql` | ✅ aplicado |
| Consulta RAG desde Python | `src/agencia/rag.py` → `buscar()`, `obtener_contexto_relevante()` | ✅ probado local y en Docker |
| Embedding de la pregunta sin torch | `src/agencia/embeddings_onnx.py` (onnxruntime + tokenizers) | ✅ idéntico a sentence-transformers (coseno 1.000000) |
| Modelo ONNX en la imagen | `scripts/descargar_modelo_onnx.py` (revisión fijada + sha256), paso en `Dockerfile` | ✅ |
| Ingesta / re-ingesta | `src/agencia/ingestar_videos.py` (dry-run por defecto, `--apply` escribe) | ✅ local (usa sentence-transformers, NO va a producción) |
| FAISS local (`data/conocimiento.faiss`) | respaldo local, ya no lo usa `rag.py` | ✅ |

**Lo que NO está hecho:** el motor no usa el conocimiento. Hoy nada en la API llama a `rag.py`.

## Lo que falta: conectar el motor

### Situación de partida
- `src/agencia/motor_ikki.py` → `AgenciaIkkiMotor.simular_campana_completa()` devuelve
  `configuracion.copys_generados` con **3 copys fijos (hardcodeados)**.
- `motor_ikki.py` importa `construir_prompt` (de `src/agencia/prompt_engineer.py`) pero **nunca lo llama**.
- `src/agencia/simulador_kimi.py:33` llama a `motor.obtener_contexto_relevante(rubro)`, que **no existe**
  en el motor → ese script hoy revienta. Es el contrato esperado: implementarlo lo arregla.
- `prompt_engineer.construir_prompt(rubro, cliente, contexto_rag)` ya arma el payload System+User y
  espera un JSON `{"titulo", "cuerpo", "cta"}` del LLM.

### Pasos propuestos
1. En `AgenciaIkkiMotor`, agregar:
   ```python
   def obtener_contexto_relevante(self, rubro: str, k: int = 3, categoria: str | None = None) -> str:
       from src.agencia.rag import obtener_contexto_relevante
       try:
           return obtener_contexto_relevante(f"anuncios para el rubro {rubro}", k, categoria)
       except Exception:
           log.exception("RAG no disponible")
           return ""   # el motor debe seguir funcionando sin RAG
   ```
   Import perezoso a propósito: no cargar onnxruntime/modelo al importar el motor.
2. Correr `python -m src.agencia.simulador_kimi` para validar contexto + prompt (no llama a ningún LLM).
3. Recién después: llamada real al LLM con `construir_prompt(...)` para reemplazar `copys_generados`,
   con **fallback a los copys fijos** si el LLM falla o no devuelve JSON válido.
4. Opcional: precargar el modelo al arrancar la API (`embeddings_onnx._cargar()` en el startup de
   FastAPI) para evitar el arranque en frío.

### Restricciones (pedidas por el usuario)
- `motor_ikki.py` y `src/agencia/api.py` están **en producción**: cambios mínimos, pedir OK antes.
- **No tocar** la lógica de casos de éxito (`obtener_caso_exito`, solo `tipo='real'`).
- El contrato de respuesta de la API (`simular_campana_completa`) no debe romperse: agregar, no quitar campos.

## Cosas que hay que saber (gotchas)

- **Prefijos e5:** pregunta = `"query: " + texto`; pasajes indexados = `"passage: " + texto`.
  `embeddings_onnx.codificar_query()` ya pone `query: `. No mezclar.
- **Pricing:** "¿Cuánto cobrar por Meta Ads?" sin filtro trae chunks de Meta, no de pricing (el término
  "Meta Ads" pesa más). Usar `categoria="Pricing_Agencia"` o reformular ("honorarios", "cuánto cobrar al cliente").
  Categorías: `Meta_Ads_Estructura`, `Google_Ads_CPC`, `Google_Ads_Estructura`, `Pricing_Agencia`, `Estrategia_General`.
- **Arranque en frío:** la 1ª consulta tarda ~8 s (carga ONNX 470 MB); las siguientes ~300 ms.
- **Modelo:** `IKKI_EMBED_MODEL_DIR` (en Docker `/app/models/multilingual-e5-small`). En local:
  `python scripts/descargar_modelo_onnx.py` lo deja en `models/` (ignorado por git/docker/railway).
- **Permisos:** `knowledge_chunks` tiene RLS sin políticas y `match_knowledge` solo es ejecutable por
  `service_role` → hay que usar `SUPABASE_SERVICE_ROLE_KEY` (como ya hace el motor).
- **Filas `youtube` viejas** en `knowledge_entries` (13, transcripciones completas, varias duplicadas de
  los videos nuevos) **no** están en `knowledge_chunks` y no aparecen en la búsqueda. Así está bien.
- Si se re-ingesta con otro modelo, hay que regenerar `knowledge_chunks` completa y actualizar
  `embeddings_onnx.py` + `scripts/descargar_modelo_onnx.py` (revisión y sha256).

## Probar

```bash
# Búsqueda contra Supabase (necesita .env y el modelo en models/)
PYTHONPATH=. venv/bin/python -m src.agencia.rag "¿Cómo bajo el costo por clic en Google Ads?"
# Esperado: ids 38, 48, 43 (similitud 0.911 / 0.904 / 0.901)

# Re-ingesta (dry-run; agregar --apply para escribir)
HF_HUB_OFFLINE=1 venv/bin/python src/agencia/ingestar_videos.py
```

## Deploy (Railway)
- Proyecto `ikki-api`, servicio `ikki-api`, dominio `ikki-api-production.up.railway.app`.
- Desde `/home/ibar/PROYECTOS/Proyectos/DepaFix`:
  `railway up --service ikki-api --environment production`
- **No** desplegar sobre el servicio/proyecto `Depafix` (es otro proyecto; pisarlo es destructivo).
