# Depafix API

## Stack técnico
| Componente | Version | Rol |
|:---|:---|:---|
| Python | 3.12 | Lenguaje base |
| FastAPI | 0.110+ | Framework Web |
| PostgreSQL | 16 | Motor de Base de Datos |
| SQLAlchemy | 2.0 | ORM y Modelos |
| Uvicorn | 0.29+ | Servidor ASGI |

## Arranque
```bash
cd ~/Proyectos/DepaFix/core && python3 main.py
sudo systemctl start depafix-api
```

## Endpoints (40 total)

### /obras (5)
| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | /obras/ | Listar todas las obras |
| POST | /obras/ | Crear nueva obra |
| PUT | /obras/{id} | Actualizar obra por ID |
| DELETE | /obras/{id} | Eliminar obra por ID |
| POST | /obras/filtrar | Filtrar obras por criterios |

### /admin (4)
| Método | Ruta | Descripción |
|--------|------|-------------|
| POST | /admin/login | Iniciar sesión |
| GET | /admin/usuarios | Listar usuarios |
| POST | /admin/usuarios | Crear usuario |
| PUT | /admin/usuarios/{id} | Actualizar usuario |

### /agentes (5)
| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | /agentes/ | Listar todos los agentes |
| POST | /agentes/ | Crear nuevo agente |
| PUT | /agentes/{id} | Actualizar agente |
| DELETE | /agentes/{id} | Eliminar agente |
| POST | /agentes/buscar | Buscar agente por filtros |

### /siegfried (5)
| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | /siegfried/causas | Listar causas legales |
| GET | /siegfried/causas/{id} | Obtener causa por ID |
| GET | /siegfried/licitaciones | Listar licitaciones |
| GET | /siegfried/auditoria/casos | Listar casos de auditoría |
| GET | /siegfried/conocimiento | Listar conocimiento vigente |

### /cobranza (5)
| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | /cobranza/clientes | Listar clientes |
| GET | /cobranza/clientes/{id} | Obtener cliente por ID |
| GET | /cobranza/facturas | Listar facturas |
| POST | /cobranza/tokens/descontar | Descontar un token |
| POST | /cobranza/tokens/recargar | Recargar tokens |

### /sence (5)
| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | /sence/cursos | Listar cursos SENCE |
| POST | /sence/cursos | Crear curso SENCE |
| PUT | /sence/cursos/{id} | Actualizar curso |
| DELETE | /sence/cursos/{id} | Eliminar curso |
| POST | /sence/generar | Generar documentos SENCE |

### /agencia (5)
| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | /agencia/campanas | Listar campañas |
| POST | /agencia/campanas | Crear campaña |
| PUT | /agencia/campanas/{id} | Actualizar campaña |
| DELETE | /agencia/campanas/{id} | Eliminar campaña |
| GET | /agencia/canales | Listar canales digitales |

### /legal (4)
| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | /legal/alertas | Listar alertas legales |
| POST | /legal/alertas | Crear alerta |
| PUT | /legal/alertas/{id} | Actualizar alerta |
| DELETE | /legal/alertas/{id} | Eliminar alerta |

### Base (2)
| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | / | Redirige a /docs |
| GET | /health | Healthcheck de la API |
## Schemas Postgres (8)
obras - siegfried - sence - legal - agencia - cobranza - agentes - auditoria

## Agentes automaticos
| Agente | Frecuencia |
|---|---|
| Aquiles | Cada 30 minutos |
| Siegfried | Cada 15 minutos |
| Sancho | Cada hora |
