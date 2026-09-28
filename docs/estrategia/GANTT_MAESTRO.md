---
titulo: Gantt Maestro DepaFix
version: 2.4
fecha: 2026-09-28
autor: ibar + DT
progreso_global: 87%
---

# 🗓️ GANTT MAESTRO — DepaFix Ecosystem

## 📊 Progreso Global: 87%

| Fase | Estado | % |
|---|---|---|
| F0-F3 Base (saneamiento, core, Kraken, procurador) | ✅ | 100% |
| F6 Ingeniero Informático (6 módulos) | ✅ | 100% |
| F8-F9 Bot Trading v2 (5 factores) | ✅ | 100% |
| F10 CEO Service | 🔄 | 90% |
| F11 Producto Inmobiliario | 🔄 | 40% |
| F12 Mercado Público | ⏸️ | 0% |
| F7 Kimi API | ⏳ | 0% |

---

## ✅ LO QUE LLEVAMOS

- CEO Service en Railway con 6 workers activos
- Bot Kraken corriendo 24/7 en paper trading ($89 intactos)
- Página web /properties-public con 372 props TocToc
- Pipeline knowledge end-to-end (YouTube → Claude → query)
- Ingeniero con health_check, auto_repair, notifier, reportes
- Supervisor_trading con kill-switch (5 reglas de riesgo)

## 🎯 LO QUE ESTAMOS HACIENDO

- Pulir supervisor_trading (fix umbral ops/hora aplicado hoy)
- Poblar knowledge_items con reglas de riesgo
- Configurar Telegram para alertas reales

---

## 📅 SEMANA 1 — 28-SEP a 4-OCT

### CEO INTELIGENTE + SUPERVISIÓN

| Día | Objetivo | Estado |
|---|---|---|
| **Lun 28** | supervisor_trading + bot_control + fix umbral | ✅ |
| **Mar 29** | Configurar Telegram (bot token + chat ID) | ⏳ |
| **Mié 30** | Analytics inmobiliario (precio/m² por comuna) | ⏳ |
| **Jue 1** | Fix import TocToc (precios realistas) | ⏳ |
| **Vie 2** | Cierre semana + decisión estratégica | ⏳ |
| **Sáb 3** | DESCANSO | — |
| **Dom 4** | DESCANSO | — |

## 📅 SEMANA 2 — 5-OCT a 11-OCT

### VALIDACIÓN DE NEGOCIO

| Día | Objetivo | Estado |
|---|---|---|
| **Lun 5** | Elegir producto ganador (Mercado Público vs Inmobiliaria) | ⏳ |
| **Mar 6** | Landing page (propuesta de valor) | ⏳ |
| **Mié 7** | Primer contacto con PYMEs constructoras | ⏳ |
| **Jue 8** | Generador de reportes express para clientes | ⏳ |
| **Vie 9** | Cierre semana + Gantt v2.5 | ⏳ |
| **Sáb-Dom** | DESCANSO | — |

---

## 🔧 WORKERS ACTIVOS (CEO Service)

| Worker | Estado | Función |
|---|---|---|
| properties_page | ✅ | Sirve HTML con propiedades |
| cleanup_old_tasks | ✅ | Limpia tasks >30 días |
| notifier_telegram | ⚠️ | Falta configurar token |
| scrape_sodimac | ⚠️ | Placeholder (selectores rotos) |
| scrape_toctoc | ✅ | 372 props cargadas |
| **supervisor_trading** | ✅ | Kill-switch con 5 reglas |

---

## 🎯 PRÓXIMAS ACCIONES (Semana 1)

1. **Mar 29** — Configurar Telegram (bot + chat ID)
2. **Mié 30** — Worker `calculate_market_stats`
3. **Jue 1** — Fix import precios irreales
4. **Vie 2** — Decisión estratégica

---

## 💰 RECURSOS

| Recurso | Estado |
|---|---|
| Tokens Claude | ~$2 USD restantes |
| Kimi API | No activada (postergada) |
| Railway | 7 servicios activos |
| Supabase | Free tier (bajo uso) |
| Kraken | $89 intactos (paper) |

---

## ⚠️ RIESGOS ACTIVOS

| Riesgo | Mitigación |
|---|---|
| Tokens Claude agotándose | Migrar a Kimi cuando haya caja |
| Umbrales mal calibrados | Ajustar según datos reales |
| Sin cliente pagando | Validar Mercado Público semana 2 |
| Dataset TocToc desactualizado | Scraper vivo (Apify pago) |

---

_Última actualización: 2026-09-28 17:00_
