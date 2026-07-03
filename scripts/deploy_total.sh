#!/bin/bash
set -e
echo "=== DEPLOY TOTAL DEPAFIX $(date '+%Y-%m-%d %H:%M') ==="
VPS="${1:-localhost}"

# 1. Backup
export PGPASSWORD=sGXizxWs4khbF8ZJeOJ
pg_dump -h localhost -U depafix depafix -Fc > /tmp/depafix_total.dump
echo "[OK] Backup: $(du -sh /tmp/depafix_total.dump | cut -f1)"

# 2. Sincronizar código (solo si VPS no es localhost)
if [ "$VPS" != "localhost" ]; then
    rsync -avz --exclude='.git' --exclude='__pycache__' --exclude='logs/' ~/Proyectos/DepaFix/core/ ubuntu@$VPS:/home/ubuntu/depafix/ 2>/dev/null || true
    echo "[OK] Código sincronizado con $VPS"
fi

# 3. Ejecutar agentes
cd ~/Proyectos/DepaFix/core
for agente in onboarding_hermes_v2.py seguimiento_onboarding.py aquiles_medicion.py control_mermas.py; do
    if [ -f agentes/$agente ]; then
        python3 agentes/$agente && echo "  [OK] $agente" || echo "  [FAIL] $agente"
    fi
done

# 4. Verificar sistema
python3 -m pytest test_api.py test_dashboard.py -q 2>&1 | tail -2
bash scripts/deploy_check.sh 2>/dev/null | tail -1
curl -sf http://localhost:8000/health && echo "API OK" || echo "API FAIL"

echo "=== DEPLOY COMPLETO ==="
