# ARQUITECTURA.md

## Diagrama ASCII

    [Cron: Aquiles(30m) Siegfried(15m) Sancho(1h) Backup(2am) Reporte(7am)]
                                |
                       [Agentes v2 Python]
                                |
    [Postgres 16: 8 Schemas] <-> [FastAPI 40+ endpoints]
    obras/siegfried/sence/       Auth API Key, 7 routers
    legal/agencia/cobranza/      systemd service
    agentes/auditoria                  |
                               [Dashboard HTML/JS]
                          8 paginas estaticas + /nav

## Flujo Licitacion Siegfried

    agentes.licitaciones (4821 filas)
    -> siegfried_licitaciones.py cada 15min
    -> filtra: plazo>0, presupuesto<1e12, palabras clave obras
    -> siegfried.alertas INSERT si no existe
    -> /siegfried/alertas API -> alertas.html
    -> si plazo <= 7 dias -> pendientes_aquiles.txt

## Decisiones Tecnicas

| Decision | Justificacion |
|---|---|
| Postgres 16 8 schemas | Aislamiento por dominio |
| Python v2 agentes | Integracion futura Claude API |
| FastAPI + systemd | Restart automatico produccion |
| Dashboard estatico | Sin framework, baja latencia |
| Cron orquestador | Fiabilidad Unix sin overhead |
| .pgpass credenciales | Sin passwords en codigo |

## Proximos Pasos

1. Claude API en Siegfried para evaluar licitaciones
2. WebSockets para notificaciones tiempo real
3. test_integracion.py flujo end-to-end
