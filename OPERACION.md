# OPERACION.md

## Verificacion matutina
bash ~/Proyectos/DepaFix/core/scripts/status_report.sh
curl -s http://localhost:8000/health
python3 -m pytest ~/Proyectos/DepaFix/core/test_api.py -q

## Ver reporte diario
cat ~/Proyectos/DepaFix/core/logs/reporte_YYYYMMDD.txt

## Ver alertas Siegfried
curl -H X-API-Key:o5CaV1gfXOhL6T9tt69oNZ8Ro6nQPppE http://localhost:8000/siegfried/alertas

## Inyectar tarea a Aquiles
echo uuid|TAREA|PRIORIDAD|params|origen >> ~/Proyectos/Agentes/pendientes_aquiles.txt

## Backup manual
bash ~/Proyectos/DepaFix/core/scripts/backup_db.sh

## Reiniciar API
sudo systemctl restart depafix-api

## Tests completos
python3 ~/Proyectos/DepaFix/core/test_integracion.py
