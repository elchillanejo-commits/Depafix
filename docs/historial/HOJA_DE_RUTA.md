# Depafix - Análisis Técnico y Hoja de Ruta

## Casos de Uso Priorizados
| Caso | Tiempo | Valor | Endpoints | Faltante |
|---|---|---|---|---|
| Auditoría presupuestos | 2 días | Alto | /obras/presupuestos | Lógica comparación APU |
| Alerta licitaciones | 3 días | Alto | /siegfried/licitaciones | Notificador externo |
| Control avance obra | 4 días | Alto | /obras | Dashboard front |
| Conciliación facturación | 3 días | Alto | /cobranza/facturas | Integración SII |
| Reporte legal | 2 días | Medio | /legal/causas | Vista resumen ejecutiva |
| Inventario dinámico | 5 días | Medio | /obras | Gestión stock |

## Prompts para Agentes (Integración futura Claude)

### Aquiles (Costos)
Eres analista técnico de obras. Recibes: uuid|MATERIAL_ID|CANTIDAD|OBRA_ID
Evalúa si la cantidad excede el presupuesto APU. Responde en JSON: {status, desviacion, accion_recomendada}

### Siegfried (Legal)
Eres consultor jurídico en obras públicas. Recibes: uuid|TIPO_DOC|URLRIORIDAD
Analiza el riesgo legal. Responde en JSON: {riesgo, resumen, recomendacion, plazo_critico}

### Sancho (Cobranza)
Eres gestor de cobranza. Recibes: uuid|CLIENTE_ID|MONTO|VENCIMIENTO
Evalúa el estado del pago. Responde en JSON: {estado, accion, notificacion_requerida, tipo_gestion}

## Plan de Testing
- Unitarios pendientes: modelos SQLAlchemy, lógica agentes v2
- Integración faltante: flujo Siegfried end-to-end, tests de auth
- Carga: Locust, límite estimado 50-80 req/seg con psycopg2 síncrono
- Prioridad crítica: agentes v2 (punto único de falla)
