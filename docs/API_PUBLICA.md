# DepaFix API Pública v2.0

## Base URL
https://breath-tigress-sighing.ngrok-free.dev

## Autenticación
Header: X-API-Key: {tu_api_key}

## Endpoints públicos
| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | /health | Estado del sistema |
| GET | /agentes/propiedades | Lista propiedades (filtros: comuna, precio_min, precio_max) |
| GET | /agentes/propiedades/{id} | Detalle propiedad |
| GET | /agentes/prediccion/arriendo | Predecir precio arriendo (comuna, m2, dormitorios) |
| GET | /agentes/marketplace/cotizar | Cotizar materiales (Sodimac, Easy, Construmart) |
| GET | /reportes/dashboard | Métricas generales |

## Ejemplos
curl -H "X-API-Key: TU_KEY" https://breath-tigress-sighing.ngrok-free.dev/agentes/propiedades?comuna=Providencia&precio_max=500000
curl -H "X-API-Key: TU_KEY" "https://breath-tigress-sighing.ngrok-free.dev/agentes/prediccion/arriendo?comuna=Santiago&m2=70&dormitorios=3"
