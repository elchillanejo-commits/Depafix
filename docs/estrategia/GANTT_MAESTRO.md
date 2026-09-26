---
titulo: Gantt Maestro DepaFix
version: 1.0
fecha: 2026-09-26
autor: ibar + Claude DT
proposito: Fuente de verdad del roadmap. Alimentar al CEO.
tags: [roadmap, gantt, planeacion]
---

# 🗓️ GANTT MAESTRO — CEO DepaFix

## 📊 Progreso Global: 85%

| Fase | Estado | % | Notas |
|---|---|---|---|
| F0-F3 Base | ✅ | 100% | Bot, procurador, infra |
| F6 Ingeniero | ✅ | 100% | 6 módulos + timers |
| F8 Bug 100% COMPRA | ✅ | 100% | Resuelto con refactor v2 |
| F9 Worker Railway v2 | ✅ | 100% | Producción 24/7 |
| F10 CEO Service | 🔄 | 95% | 12 workers activos |
| F11 Producto Inmobiliario | 🔄 | 40% | Dataset TocToc cargado |
| F12 Mercado Público | ⏸️ | 0% | Pausado |
| F7 Kimi API | ⏳ | 0% | Pendiente |

---

## 🚧 PENDIENTE MAÑANA (Lunes simulado)

### 1. Kutt Property Scraper (prioridad ALTA)
- **Contexto:** Soy corredor, tengo login en `plataforma.kutt.cl`
- **Descubierto:**
  - Base URL: `https://plataforma.kutt.cl/`
  - Endpoint conocido: `/OrdenVentaArriendo/GetConfigOrden?tipo=1&idCorredora=85`
  - Requiere autenticación (HTTP 401 sin cookie)
  - Patrón API: .NET MVC clásico (`/Controller/Method`)
- **Plan:**
  - Creado `ceo/workers/kutt.py` (Playwright con login)
  - Falta: cargar `KUTT_USER` + `KUTT_PASS` en .env + Railway
  - Falta: test local y ajuste de selectores
- **Hallazgos clave:**
  - Botón "Descargar cartera" en la UI (alternativa rápida)
  - DevTools → Network → Copy as cURL (si se necesita cookie)

### 2. Revisar HILO_CONDUCTOR
- Verificar que las últimas sesiones están registradas
- Limpiar duplicados
- Consolidar pendientes

### 3. "Nutrición del sistema"
- La carpeta `~/Documentos/CEO_DepaFix/` es el nuevo repo de documentación estratégica
- Objetivo: alimentar al CEO con contexto para decisiones futuras
- Próximos documentos: HILO.md, ROADMAP.md, METRICAS.md

---

## 📅 SEMANA ACTUAL

| Día | Tarea | Estado |
|---|---|---|
| Vie 25 | CEO 9 workers + pipeline knowledge | ✅ |
| Sáb 26 (hoy) | Dataset TocToc + intento scrapers | ✅ |
| Dom 27 | DESCANSO | — |
| Lun 28 | Kutt scraper + HILO review | ⏳ |
| Mar 29 | Configurar Telegram | ⏳ |
| Mié 30 | Analytics (precio/m² por comuna) | ⏳ |
| Jue 1 | Web profesional con datos reales | ⏳ |
| Vie 2 | Cierre semana + Gantt | ⏳ |

---

## 🎯 SEMANA 2 (2-8 oct): Producto vendible

- Publicar página web de propiedades
- SEO básico (meta tags, sitemap)
- Alertas automáticas (nuevas props bajo precio)
- Reporte semanal por email
- Dominio propio

---

## 🔴 RIESGOS ACTIVOS

| Riesgo | Impacto | Mitigación |
|---|---|---|
| Portales bloquean scraping | Alto | Dataset público + Kutt propio |
| Keys expiran | Medio | Rotación mensual |
| Claude API sin cap | Alto | Configurar hard-cap $2/día |
| Single point of failure (Vostro) | Alto | CEO en Railway + health check |

---

## 💰 TOKENS CLAUDE

- Gastado: ~$12
- Restante: ~$2
- Estrategia: migrar a Kimi API en 2 semanas

---

## 🎁 ACTIVOS DIGITALES

1. **CEO Service** → 12 workers en Railway
2. **Knowledge base** → 8 items procesados
3. **Properties** → 19 propiedades (5 manuales + 14 TocToc)
4. **Bot trade** → 33% COMPRA / 33% VENTA / 34% ESPERA
5. **Kraken** → $89 intacto
6. **Repo** → github.com/elchillanejo-commits/Depafix

---

_Última actualización: 2026-09-26 22:50_

---

## 💰 INVERSIÓN EN SCRAPING (Postergado)

**Decisión:** NO invertir en servicios pagados hasta que haya caja.

**Servicios evaluados (para retomar cuando negocio facture):**
- **Apify** → $4/1K listings (MLC/Yapo/Portales LATAM)
- **ScrapingBee** → $49.99/mes (250K créditos)
- **Bright Data** → $1.50/1K requests (5K gratis/mes)
- **ZenRows** → $19/mes (45K créditos)

**Trigger para retomar:** primer cliente pagando $100+/mes.

**Mientras:** usar dataset TocToc (367 props reales ya disponibles) + API oficial MercadoLibre (gratis).

---

## 📅 SEMANA ACTUAL (28-sep a 4-oct)

| Día | Tarea | Estado |
|---|---|---|
| Lun 28 | Kutt scraper (DESCARTADO) + HILO review | ✅ Cerrado |
| **Mar 29** | **Configurar Telegram + notifier** | 🔄 HOY |
| Mié 30 | Analytics (precio/m² por comuna) | ⏳ |
| Jue 1 | Web profesional con datos reales | ⏳ |
| Vie 2 | Cierre semana + Gantt | ⏳ |
