# CHANGELOG.md
### 30-JUNIO-2026
- [Infraestructura] Migracion SQLite a Postgres 16 (8 schemas)
- [Agentes] Despliegue Agentes v2 Python (Aquiles, Siegfried, Sancho)
- [API] FastAPI 40 endpoints + Auth API Key + systemd
- [Dashboard] Portal 6 paginas estaticas + /nav
- [QA] 12 tests unitarios pasando
- [Backup] Backup automatico 2am configurado

### 01-JULIO-2026
- [Siegfried] Modulo siegfried_licitaciones.py deteccion proactiva (4 alertas)
- [API] Expansion a 50 endpoints, router reportes, router alertas
- [Dashboard] alertas.html con badges y filtros
- [Reporte] reporte_diario.sh a las 7am con psql
- [QA] test_integracion.py 4/4 + 16 tests total
- [Doc] ARQUITECTURA.md con diagrama ASCII

### 01-JULIO-2026 (tarde)
- [Auth] Multi-usuario: tabla public.usuarios, POST /auth/register, POST /auth/login, GET /auth/verify, GET /auth/usuarios
- [Auth] JWT handler: crear_token() y verificar_token() en auth/jwt_handler.py
- [Middleware] Auth acepta master key + keys de tabla usuarios + Bearer JWT
- [API] 27 tests pasando (api + dashboard + integracion)
- [Admin] Endpoint /admin/metricas con CPU y memoria via psutil
- [Backup] Script corregido: excluye schemas public, usa 8 schemas propios
- [Scripts] monitor_agentes.py, verificar_backups.sh, resumen_dia.sh, rotacion_logs.sh
- [Nav] 12 páginas en portal: SENCE, Admin, Nueva Obra, Evaluaciones IA agregadas

### 01-JULIO-2026 (noche)
- [Auth] JWT handler: crear_token() verificar_token() en auth/jwt_handler.py
- [Auth] POST /auth/login devuelve api_key + token JWT
- [Middleware] auth.py acepta Bearer JWT además de X-API-Key
- [Middleware] auditoria.py registra cada request en auditoria.accesos_api
- [DB] Índices auditoría + vistas v_errores_recientes + v_uso_por_usuario
- [Tests] 27 tests pasando (api + dashboard + integracion)
- [Scripts] resumen_dia.sh, rotacion_logs.sh en crontab
- [Health] health_check.py todos los checks OK

### 01-JULIO-2026 (noche)
- [Auth] Bearer JWT en middleware + JWT en response de /auth/login
- [Auth] /auth/login excluido del middleware (no requiere key)
- [Middleware] auditoria.py registra requests en auditoria.accesos_api
- [Admin] /admin/metricas con CPU% y memoria% via psutil
- [Scripts] resumen_dia.sh, rotacion_logs.sh
- [Dashboard] login.html, estado_sistema.html
- [Tests] 27 tests pasando

### 01-JULIO-2026 (cierre)
- [Tests] 30 tests pasando (api:9 + dashboard:11 + integración:10)
- [Auth] Bearer JWT en middleware + token
- [Monitoreo] Script monitor_sistema.sh cada 5 min (API, agentes, disco, errores 401)
- [Telegram] Notificaciones vía Telegram para alertas críticas

### 02-JULIO-2026 (madrugada)
- [x] Hermes scraping Portal Inmobiliario integrado (430 propiedades en BD)
- [x] /agentes/hermes/estado y /agentes/hermes/ejecutar endpoints
- [x] /agentes/propiedades con filtros por comuna, precio, dormitorios
- [x] /obras/medir endpoint + aquiles_medicion.py (modo CLI + función)
- [x] control_mermas.py: 18 mermas detectadas, registradas en memoria_agentes
- [x] foto_parser.py: naming convention 01_cocina.jpeg → zona Cocina
- [x] medicion.html dashboard de presupuesto pintura
- [x] hermes.html portal de mercado inmobiliario
- [x] SKILL_licitaciones_chile.md para Siegfried en radier
- [x] GANTT.md con tareas completadas y pendientes semana 3-4
- [x] API.md documentación pública de endpoints
- [x] MaquiaveloBase template FastAPI reutilizable
- [x] Deploy Check: 61 endpoints, 35 tests pasando, 0 errores

### 02-JULIO-2026 (cierre — 18:45)
- [x] presupuesto_cliente.html imprimible con parámetros URL
- [x] ngrok instalado (falta authtoken en ~/.ngrok_authtoken)
- [x] Gantt en Postgres + endpoint /agentes/gantt + gantt.html dashboard
- [x] deploy_gestalt.sh funcional para VPS Hetzner
- [x] medicion.html con sección de documentos generados (URL cliente)
- [x] control_mermas.py 18 mermas detectadas, inventario en memoria_agentes
- [x] fix presupuesto_id en aquiles_medicion.py (secuencia sincronizada)
- [ ] Pendiente: ngrok authtoken, GitHub Pages, SSL certbot

## [2026-07-02] - Cierre de iteración 3 (Hermes)
### 1 de julio
- Finalización de módulo de calidad.
- Correcciones en scripts de despliegue.
### 2 de julio
- Pruebas exitosas y cierre de Gantt.
- Resumen de Hermes generado en cierre_hermes_resumen.txt.
