# Pruebas de fuego — Sandbox DepaFix

**Fecha:** 2026-10-29  
**Entorno:** `/home/ibar/DepaFix_Maestro`  
**Motor de síntesis:** Kimi K3.1 Pro (`moonshot/kimi-k3.1-pro`)  
**Embeddings:** `intfloat/multilingual-e5-small` (384 dims)  
**Cerebros:** FAISS locales + `metal_knowledge` en Supabase

> **Nota técnica:** `kimi-k3.1-pro` rechaza `temperature=0` y `0.7` con HTTP 400 ("only 1 is allowed for this model"). Las pruebas se ejecutaron con `temperature=1`. Esto afecta a `mente_360.py` (usa 0) y `agente_ceo.py` (usa 0.7).

---

## Prueba 1 — Cerebro Agua

**Pregunta:** ¿Cuáles son los 3 productos más rentables para dropshipping este año?

**Cerebro consultado:** `data/agua.faiss` — 2.076 fragmentos, 16 documentos.  
**Fuentes recuperadas:** Curso Shopify Dropshipping 2026 (guía completa), Wikipedia Dropshipping, campañas Meta Ads 2026, landing pages con IA.

### Respuesta

1. **Escalera plegable** — Categoría: herramientas y mejoras para el hogar. Señal: nicho descrito como "oportunidad gigantesca", con productos de "ticket alto" cuyas ventas "generan más ganancias" y son menos tediosas de gestionar que muchas ventas pequeñas. La señal es de categoría, no un margen individual comprobado.

2. **Licuadora portátil** — Categoría: cocina y comedor. Señal: se menciona expresamente como producto en tendencia y "producto ganador"; las licuadoras figuran entre "los mejores productos de dropshipping" de esa categoría.

3. **Rodillo facial** — Categoría: belleza y cuidado personal. Señal: está incluido entre los productos que "más venden" y los "más ganadores" del nicho, que el instructor presenta como uno con alta facturación.

**Nota:** El cerebro no contiene un ranking 2026 verificable ni márgenes, costes o ventas comparables por producto; la lista de Shopify citada corresponde a 2024. Faltan datos 2026 de demanda, precio, coste, margen y ventas efectivas para afirmar cuáles son realmente los tres más rentables.

### Veredicto

**APROBADO CON RESERVA.** La respuesta es trazable al contexto y no inventa cifras, pero el cerebro no tiene un ranking anual: es una síntesis de señales, no una verdad de mercado 2026.

---

## Prueba 2 — Cerebros Tierra + Metal

**Perfil:** contacto de Construcción, eneatipo 8w7.  
**Objetivo:** ofrecer un "Diagnóstico de Admisibilidad" para licitaciones.

### Contexto recuperado

| Fuente | Estado | Qué se recuperó |
|---|---|---|
| Tierra (`data/tierra.faiss`) | ⚠️ Contaminado | 1.858 fragmentos, pero de **trading/cripto** ("Curso de CRIPTOMONEDAS", "Las matemáticas del trading", "Plan de trading"). No contiene el dossier de construcción. |
| Metal local (`data/metal.faiss`) | ⚠️ Etiqueta distinta | 5.404 fragmentos de **filosofía/estrategia** (Sun Tzu, Maquiavelo, Marco Aurelio, ventas). No es el Metal legal. |
| Metal legal (Supabase `metal_knowledge`) | ✅ | 7.011 filas. Mejor match: `plantilla_pitch_constructora.txt` (pitch B2B eneatipo 8, Auditoría Legal Express). |
| Dossier construcción (`data/dossier_construccion_8w7.md`) | ✅ pero no indexado | 6 dolores + guion de 20 min. Se usó como sustrato de construcción. |
| Speech aprobado (`data/speeches.csv`, `S_CONSTR_001`) | ✅ | Referencia de tono 8w7 para licitaciones. |

### Speech de WhatsApp (listo para copiar/pegar)

```text
Te escribo directo: si los anexos no calzan con las bases o la boleta GSO sale observada por monto, beneficiario o plazo, puedes quedar fuera antes de competir; quiero revisar contigo dónde se está filtrando ese riesgo.

El Diagnóstico de Admisibilidad es una revisión asistida de una licitación real para cruzar bases, anexos y GSO y dejarte una lista clara de faltantes e inconsistencias; no reemplaza tu criterio, no garantiza adjudicación y no borra multas.

¿Te acomoda mañana a las 9:30 o el jueves a las 16:00 para 20 minutos? Tú decides; si no es prioridad, dime "no ahora" y lo dejamos ahí.
```

### Chequeo 8w7

- [x] Directo, sin adulación ni rodeos.
- [x] Dolor concreto: anexos + boleta GSO (monto, beneficiario, plazo).
- [x] Define el diagnóstico en una frase.
- [x] Límites explícitos: no reemplaza su criterio, no garantiza adjudicación, no borra multas.
- [x] CTA con dos opciones de horario y permiso para decir "no ahora".
- [x] Sin emojis, bullets ni markdown.
- [x] Él mantiene el control de la decisión.

### Veredicto

**APROBADO en forma; CRÍTICO en arquitectura de datos.** El speech cumple el perfil 8w7 y evita sobreventa, pero **Tierra no contiene construcción** y **Metal local no es legal**: el resultado se sostuvo con el dossier y el pitch de Supabase, no con los índices que el router dice usar.

---

## Hallazgos técnicos

1. **`temperature` incompatible con Kimi K3.1 Pro.** La API solo acepta `temperature=1`; `mente_360.py` usa `0` y `agente_ceo.py` usa `0.7`. Ambos fallarían al sintetizar con este modelo. Recomendación: usar `1` y subir `max_tokens` (el modelo consume tokens en razonamiento; con 1.600 puede devolver contenido vacío).
2. **Etiquetas cruzadas.** `mente_360.py` dice Tierra=Construcción y Metal=Legal. `agente_ceo.py` dice Tierra=Trade y Metal=Filosofía/Eneagrama. Los índices reales siguen a `agente_ceo`: `tierra.faiss` es trading y `metal.faiss` es filosofía/estrategia.
3. **Dossier de construcción no indexado.** `data/dossier_construccion_8w7.md` (6 dolores + guion) no está en `tierra.faiss` ni en `conocimiento_360.faiss`. El router de Tierra no lo puede recuperar.
4. **Metal legal vive en Supabase, no en el FAISS.** `data/metal.faiss` no contiene la normativa legal; `metal_knowledge` en Supabase sí (7.011 filas). Son dos "Metal" distintos con el mismo nombre.
5. **`test_agua.py` usa embeddings incompatibles.** Carga `OpenAIEmbeddings` (1.536 dims) contra un índice de 384 dims (`multilingual-e5-small`). La consulta fallará por dimensión. Usar `HuggingFaceEmbeddings(model_name="intfloat/multilingual-e5-small")`.

---

## Recomendaciones

1. Reindexar `tierra.faiss` con `dossier_construccion_8w7.md`, `plantilla_pitch_constructora.txt` y documentos de licitaciones/ChileCompra.
2. Decidir una sola identidad para Metal: o se ingesta el legal de Supabase al FAISS, o se renombra el Metal local a "Filosofía/Estrategia".
3. Corregir `mente_360.py` y `agente_ceo.py` a `temperature=1` y `max_tokens` ≥ 3.000.
4. Añadir un guardrail de "ranking anual": si el contexto no tiene datos del año, la respuesta debe declararlo (ya ocurrió en la Prueba 1).
5. Unificar el mapa de cerebros en un solo archivo de configuración para que router, agentes y scripts no se contradigan.

---

## Cómo se generó

- Retrieval: `FAISS.load_local` + `HuggingFaceEmbeddings("intfloat/multilingual-e5-small")`, `similarity_search` con k=3–4 por consulta y deduplicación.
- Metal legal: RPC `match_metal_knowledge` en Supabase con `SentenceTransformer` y `normalize_embeddings=True`.
- Síntesis: `POST https://api.moonshot.ai/v1/chat/completions`, modelo `kimi-k3.1-pro`, `temperature=1`.
- Archivos de contexto: `data/agua.faiss`, `data/tierra.faiss`, `data/metal.faiss`, `data/dossier_construccion_8w7.md`, `data/speeches.csv`.
