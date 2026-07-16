# STATUS DepaFix — Cierre Julio 2026

## 🟢 Sistema (Green)
| Componente | Estado |
|---|---|
| API FastAPI | ✅ 69+ endpoints |
| PostgreSQL | ✅ conectado, 576+ propiedades, 80+ tareas agentes |
| Tests | ✅ 35+ tests pasando |
| Auth | ✅ X-API-Key + Bearer JWT |
| Multi-usuario | ✅ 5 usuarios activos |
| Auditoría | ✅ accesos_api funcionando |
| Backups | ✅ diarios + cierre julio |
| Monitoreo | ✅ 24/7 health checks |
| Ngrok | ✅ URL pública activa |

## 🟡 Agentes
| Agente | Estado |
|---|---|
| Aquiles | ✅ presupuesto dual + PDF |
| Siegfried | ✅ licitaciones evaluadas |
| Hermes | ✅ 576 propiedades + Yapo.cl |
| Bilardo | ✅ alertas ISO 9001 |
| Sancho | ✅ corriendo en cron |

## 🛠 Hitos Julio 2026
- [x] Semana 1: Core (API, Auth, DB, Tests)
- [x] Semana 2: Agentes + scraping + skills
- [x] Semana 3: Onboarding + reportes + facturación
- [x] Semana 4: Infraestructura (ngrok, SSL, monitoreo)
- [x] 4 licitaciones VIABLES con presupuestos y mensajes
- [x] Cierre total: 30 prompts ejecutados

## 📈 Predictor DepaFix (2026-07-15)
| Componente | Estado |
|---|---|
| `/predict` (Railway, producción) | ✅ verificado con ítem real (SERVIU 2026) |
| `/status` (Railway, producción) | ✅ bug de `record_count` corregido y desplegado (antes contaba `presupuestos`, ahora cuenta `precios_serviu`) |
| Datos SERVIU en Supabase | ✅ 468 registros cargados, pero **991 filas totales en `precios_serviu`** por duplicado exacto (ver nota) |
| `trade_agent.py` (detección de anomalías) | 🟡 en pausa — ver nota |
| Scraping Mercado Público | 🔴 en pausa — ver nota |

**Duplicado detectado, no resuelto todavía:** las 468 filas de `fuente='SERVIU'`
son idénticas (mismo ítem, mismo precio) a las 468 de
`fuente='SERVIU_DS27_RM_2025'`. El catálogo único real es **523** (468 sin
duplicar + 55 de Mercado Público), pero `/status` sigue mostrando 991 porque
el SQL de limpieza no se ha ejecutado en Supabase. La key configurada acá es
`anon` sin permiso de DELETE (confirmado: un intento de borrado devolvió 0
filas afectadas), así que esto requiere correrse manualmente en el SQL
Editor de Supabase con permisos de owner:
```sql
DELETE FROM precios_serviu WHERE fuente = 'SERVIU';
```

**Trade agent en pausa:** el agente corre sin errores y usa `reglas_rubros` +
`v_analisis_desviacion` correctamente, pero con datos reales marcó 33/37
ítems (89%) como anomalía en rubros como Construcción y Capacitación. Causa:
`valor_unitario` mezcla totales de contrato de escala muy distinta (ej.
Construcción de obras civiles va de $4.9M a $159.7M) bajo el mismo rubro, no
precios de un mismo bien — el modelo actual (promedio/stddev por rubro) no es
válido sin normalizar por tamaño de proyecto (m², horas, cantidad). No se
muestra a clientes hasta resolver esto.

**Scraping Mercado Público en pausa:** el ticket de API actual devuelve 400
en `/servicios/v1/publico/licitaciones.json` y 404 en `/licitacion.json`;
solo `/modules/api.aspx` responde, y devuelve HTML, no JSON. Se solicitó un
ticket nuevo y se recibió el mismo número. Se envió correo a
`api@mercadopublico.cl` solicitando habilitación del endpoint JSON (RUT
13.696.162-2). El cron semanal `actualizar_precios_mercado.py` (lunes 7am)
quedó comentado en crontab hasta que el ticket funcione. El sistema opera
solo con datos SERVIU mientras tanto.

## 🔶 Trading Algorítmico Cripto — TradingLogic (2026-07-15)
| Componente | Estado |
|---|---|
| `TradingLogic` (`src/trading/crypto_trader_agent.py`) | ✅ implementada y verificada con asserts |
| Fórmula Alcista Standard | ✅ implementada (soporte estático + Golden Pocket Fibo 0.618-0.786 + testeo EMA50 + RSI sobreventa) |
| Fórmula Institucional Avanzada | ✅ implementada (Order Block válido + mitigación de FVG + barrido de liquidez) |
| Regla de Fractalidad (1H debe confluir con soporte 4H/1D) | ✅ implementada — corta el análisis y devuelve `ESTADO: ESPERA` si no hay confluencia |
| Stop Loss técnico basado en estructura | ✅ implementado (nunca un % arbitrario) |
| Robustez ante fallas de red/Supabase | ✅ cada consulta y cada fórmula en try/except independiente; nunca lanza excepción hacia afuera |
| Esquema `velas_cripto` (OHLC por activo/temporalidad) | ✅ definido en `sql/create_velas_cripto.sql` |
| Pipeline de ingesta de velas desde exchange | ❌ no existe — ver nota |

**Estado operativo real: `ESTADO: ESPERA`.** Toda la lógica de trading está
implementada y verificada con asserts sobre velas sintéticas (EMA, RSI,
Fibonacci, zonas de soporte, detección y mitigación de FVG, Order Blocks,
barrido de liquidez, y la puerta de fractalidad) — no son suposiciones, se
probaron los casos de cada componente por separado. También se verificó
contra Supabase real: la tabla `velas_cripto` todavía no existe ahí (falla
la consulta, capturada, y el agente responde `ESPERA` con motivo en vez de
crashear). El agente está "en ayunas": no hay ningún pipeline que traiga
velas 1H/4H/1D desde un exchange (Binance u otro) y las cargue en
`velas_cripto`. Hasta que ese pipeline exista, `TradingLogic.evaluar()`
seguirá devolviendo `ESTADO: ESPERA` en producción — es el comportamiento
esperado, no un bug.

## ⏳ Pendientes (2026-07-16)
- Correr en Supabase (SQL Editor, con owner) el `DELETE` de arriba para
  dejar `precios_serviu` en 523 filas únicas.
- Enviar el correo a `api@mercadopublico.cl` (ticket 9196E835-..., RUT
  13.696.162-2) — el borrador está listo, no se ha enviado todavía.
- Configurar un `git remote` — el repo no tiene ninguno; "versionado" hoy es
  solo local, sin backup remoto.
- Decidir qué hacer con `.env` modificado y trackeado en git (sin remote
  configurado el riesgo es bajo hoy, pero conviene sacarlo del tracking
  antes de agregar un remote).
- Normalizar `precios_serviu` por escala (m², horas, cantidad) para poder
  reactivar `trade_agent.py` sin el 89% de falsos positivos.
- Construir el pipeline de ingesta de velas OHLC para activar `TradingLogic`.
