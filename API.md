# DepaFix API
Base URL: http://localhost:8000
Auth: Header X-API-Key o Authorization: Bearer {token}

## Autenticación
POST /auth/login → {email, password} → {api_key, token, rol}
GET /auth/verify?api_key=XX → {id, email, rol}

## Obras
GET /obras/presupuestos → lista paginada
GET /obras/resumen → {total, monto_total, promedio}
GET /obras/por-estado → [{estado, cantidad, total}]
POST /obras/presupuestos → {cliente, total, descripcion} → {id, cliente, total}

## Agentes
POST /agentes/tarea/aquiles → {uuid, tarea, prioridad, params, origen}
POST /agentes/tarea/siegfried → mismo formato
GET /agentes/memoria → lista de tareas procesadas

## Siegfried
GET /siegfried/alertas → lista de alertas activas
GET /siegfried/licitaciones → lista paginada
GET /siegfried/evaluaciones → evaluaciones LLM

## Reportes
GET /reportes/resumen-obras → por estado
GET /reportes/top-clientes → top 10
GET /reportes/alertas-criticas → alertas ALTO/CRITICO

## Ejemplos curl
curl -H "X-API-Key: TU_KEY" http://localhost:8000/obras/presupuestos
curl -H "Authorization: Bearer TU_TOKEN" http://localhost:8000/obras/presupuestos
