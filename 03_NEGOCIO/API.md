# DepaFix API v2.0
Base URL: http://localhost:8000
Auth: X-API-Key header

## Endpoints públicos
- GET /health
- GET /reportes/metrics
- GET /static/*

## Autenticación
- POST /auth/login
- POST /auth/register
- GET /auth/verify

## Obras
- GET /obras/presupuestos
- POST /obras/presupuestos
- GET /obras/presupuestos/{id}
- POST /obras/pagar/{id}
- POST /obras/facturar/{id}
- GET /obras/balance-general
- GET /obras/inventario-mermas

## Agentes
- GET /agentes/memoria
- GET /agentes/hermes/estado
- POST /agentes/hermes/ejecutar
- GET /agentes/propiedades
- GET /agentes/prediccion/arriendo
- POST /agentes/portal/login

## Siegfried
- GET /siegfried/alertas
- GET /siegfried/licitaciones
- GET /siegfried/licitaciones/evaluar

## Reportes
- GET /reportes/dashboard
- GET /reportes/balance
- GET /reportes/resumen-obras
- GET /reportes/top-clientes
