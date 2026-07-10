#!/bin/bash
set -e
VPS="${1:?Falta IP del VPS}"
echo "=== DEPLOY GESTALT → $VPS $(date '+%Y-%m-%d %H:%M') ==="
export PGPASSWORD=sGXizxWs4khbF8ZJeOJ
# Backup local
pg_dump -h localhost -U depafix depafix -Fc > /tmp/depafix_deploy.dump
# Sincronizar código
rsync -avz --exclude='.git' --exclude='__pycache__' --exclude='logs/' ~/Proyectos/DepaFix/core/ ubuntu@$VPS:/home/ubuntu/depafix/
# Subir BD
scp /tmp/depafix_deploy.dump ubuntu@$VPS:/tmp/
# Restaurar remoto
ssh ubuntu@$VPS "cd /home/ubuntu/depafix && pip3 install -r requirements.txt -q && pg_restore -h localhost -U depafix -d depafix /tmp/depafix_deploy.dump && sudo systemctl restart depafix-api"
echo "=== DEPLOY COMPLETO: https://gestalt.cl ==="
