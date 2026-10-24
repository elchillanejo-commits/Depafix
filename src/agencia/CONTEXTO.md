# CONTEXTO — Agencia IKKI (`src/agencia/`)
Fecha: 2026-10-24 · Basado en la lectura del código. Lo que no está claro se marca como *por confirmar*.

## 1. ¿Qué hace IKKI?
IKKI es un motor de **simulación y propuesta de campañas de marketing digital** para pymes. A partir del cliente, el rubro
y el presupuesto de pauta, calcula la economía de la agencia (fee fijo de $150.000 + 15% de comisión sobre la pauta),
reparte el presupuesto en embudos B2C/B2B con estructura **CDA**, proyecta impresiones, clics y leads con benchmarks,
y genera un plan de 30 días y creatividades. La API (FastAPI) expone la simulación y el registro de leads, y el dashboard
(Streamlit) convierte el resultado en una propuesta PDF/HTML para el prospecto y lleva un mini-CRM.

## 2. Flujo end-to-end
```
Dashboard Streamlit (cliente, rubro, presupuesto)  ──POST /api/v1/simular──▶  API en Railway (ikki-api-production)
   └─ API: ProspectoLegacy → SimulacionRequest (solo B2C, persistir=False) → MotorCDA.simular()
        └─ motor_cda + cda + benchmarks: fee, CDA, proyecciones, plan_30_dias, creatividades (sin LLM ni Supabase)
   ◀─ JSON "campaña_generada" (caso_exito = {} fijo en el código)
Dashboard → generar_html() → xhtml2pdf → descarga PDF/HTML · botón "Crear en Meta Ads" → MetaAdsIntegrator (sandbox simulado)
```
Ruta principal nueva: `POST /agencia/ikki/simular` (B2C + B2B). Si `persistir=true` → `RepositorioIkki` hace upsert en Supabase.
`POST /agencia/ikki/leads` → `leads_ikki`.

## 3. Tablas de Supabase
| Tabla | Quién la usa | Operación |
|---|---|---|
| `campanas_ikki` | repositorio_ikki.py | upsert (`grupo_simulacion_id, embudo`) |
| `presupuestos_ikki` | repositorio_ikki.py | upsert (`grupo_simulacion_id, embudo`) |
| `leads_ikki` | repositorio_ikki.py | insert, o upsert por `idempotency_key` |
| `campanas_meta` | dashboard.py (pestaña CRM) | select / update `estado` |
| `casos_exito` | motor_ikki.py (`AgenciaIkkiMotor.obtener_caso_exito`) | select. **Vacía** |
| `benchmarks_ads`, `matriz_plataforma` | motor_ikki.py (`AgenciaIkkiMotor`) | select |

Que estas tablas existan en Supabase con las columnas que espera el código está *por confirmar* (el DDL está en `07_IKKI_MARKETING/sql/` y `scripts/*.sql`).

## 4. Corazón vs. auxiliares
- **Corazón:** `api.py`, `motor_cda.py`, `cda.py`, `benchmarks.py`, `esquemas.py`, `repositorio_ikki.py`, `dashboard.py`.
- **Auxiliares/legado:** `motor_ikki.py` (la API solo usa `MotorIkki` y `FeeAgenciaRequest`; `AgenciaIkkiMotor`, que lee
  casos_exito, benchmarks_ads y matriz_plataforma, no se usa desde la API), `meta_ads_integrator.py` (sandbox, sin llamadas reales),
  `prompt_engineer.py` + `prompts/ikki_system.txt` (prompt genérico; no se ve un LLM en el flujo actual),
  `nutriente/auto_nutriente/local_brain/seed_knowledge/procesar_conocimiento` (ingesta a `data/`),
  `generar_*`, `simulador_kimi.py`.

## 5. Qué falta para que funcione end-to-end
1. **El dashboard y la API no comparten tablas:** la API escribe en `campanas_ikki`, el CRM lee `campanas_meta`, y `/api/v1/simular`
   usa `persistir=False`. El mensaje "¡Campaña generada y guardada!" del dashboard no es cierto.
2. **El caso de éxito nunca llega al PDF:** `/api/v1/simular` devuelve `caso_exito: {}` fijo y `MotorCDA` no consulta `casos_exito`.
   Llenar la tabla (ver `importar_casos.py`) no basta: también hay que conectarla en el motor o la API.
3. Los benchmarks del flujo nuevo están en el código (`benchmarks.py`), no vienen de `benchmarks_ads`. Si se busca que coincidan con Supabase: *por confirmar*.
4. El dashboard apunta a la URL fija de Railway: los cambios locales no se ven en el dashboard hasta que se despliegan.
5. Meta Ads: solo existe el sandbox simulado; faltan `META_ACCESS_TOKEN` / `META_AD_ACCOUNT_ID` (no están en `.env`) y el SDK.
6. Hay 5 archivos centrales sin trackear en git (`motor_cda`, `cda`, `esquemas`, `benchmarks`, `repositorio_ikki`). Si el deploy en Railway
   incluye la versión 2.0.0 de la API: *por confirmar*.
7. RLS y políticas de las tablas `*_ikki`: pendientes (Día 3 del GANTT).

## Variables de `.env` (solo nombres)
`SUPABASE_URL`, `SUPABASE_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `KRAKEN_API_KEY`, `KRAKEN_SECRET_KEY`, `KUTT_USER`, `KUTT_PASS`,
`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`.
El código lee además `IKKI_USE_MOCK` (por defecto "1") y `META_ACCESS_TOKEN` / `META_AD_ACCOUNT_ID`, que **no están** en `.env`.
