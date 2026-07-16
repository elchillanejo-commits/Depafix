#!/bin/bash
# setup_scraper.sh - Configura scraper de Mercado Público y cron en un solo paso

set -e

echo "🔧 Configurando scraper de Mercado Público..."

# 1. Verificar ticket actual en .env
CURRENT_TICKET=$(grep MERCADO_PUBLICO_API_KEY .env | cut -d '=' -f2 | tr -d ' "')
if [ -z "$CURRENT_TICKET" ] || [ "$CURRENT_TICKET" = "9196E835-EE53-4335-B548-716FBA4BD639" ]; then
    echo "⚠️ Ticket actual no es válido o es el de prueba."
    echo "👉 Ve a https://api.mercadopublico.cl y solicita un nuevo ticket (gratis, con Clave Única)."
    echo "📋 Pega aquí el nuevo ticket (sin comillas, sin espacios) y presiona Enter:"
    read -r NEW_TICKET
    if [ -z "$NEW_TICKET" ]; then
        echo "❌ No se ingresó ticket. Saliendo."
        exit 1
    fi
    # Actualizar .env
    sed -i "s/^MERCADO_PUBLICO_API_KEY=.*/MERCADO_PUBLICO_API_KEY=$NEW_TICKET/" .env
    echo "✅ .env actualizado con el nuevo ticket."
    export MERCADO_PUBLICO_API_KEY="$NEW_TICKET"
else
    echo "✅ Ticket actual: ${CURRENT_TICKET:0:10}..."
    export MERCADO_PUBLICO_API_KEY="$CURRENT_TICKET"
fi

# 2. Probar scraper con un rubro pequeño
echo "🧪 Probando scraper con rubro 'Construcción' (límite 3)..."
TEST_OUTPUT=$(mktemp)
python3 scrapers/mercado_publico.py --rubro "Construcción" --estado adjudicada --limite 3 --salida "$TEST_OUTPUT" 2>&1

if grep -q "400 Client Error" <<< "$TEST_OUTPUT"; then
    echo "❌ Error 400: El ticket no es válido o no tiene permisos."
    echo "   Verifica que el ticket sea correcto y que la API esté activa."
    exit 1
elif grep -q "200 OK" <<< "$TEST_OUTPUT" || grep -q "Extraídos" <<< "$TEST_OUTPUT"; then
    echo "✅ Scraper funciona correctamente."
else
    echo "⚠️ La prueba no fue concluyente. Revisa el error manualmente:"
    echo "$TEST_OUTPUT"
    exit 1
fi

# 3. Crear el script de ejecución diaria
cat > scrapers/ejecutar_mercado_diario.sh <<'SCRIPT_EOF'
#!/bin/bash
cd /home/ibar/Proyectos/DepaFix
source venv/bin/activate
RUBROS=("Construcción" "Electricidad" "Fontanería" "Gráfica" "Capacitación")
mkdir -p datos/mercado_historico
echo "🚀 Scraper diario - $(date '+%Y-%m-%d %H:%M:%S')"
for RUBRO in "${RUBROS[@]}"; do
    echo "🔍 $RUBRO"
    python3 scrapers/mercado_publico.py --rubro "$RUBRO" --estado adjudicada --limite 20 --salida "datos/mercado_historico/${RUBRO}_$(date +%Y%m%d).json"
    sleep 1
done
echo "📤 Cargando a Supabase..."
python3 -c "
import sys, json, glob
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))
from core.db_manager import db
from datetime import datetime
archivos = glob.glob('datos/mercado_historico/*.json')
nuevos = 0
for arch in archivos:
    with open(arch, 'r', encoding='utf-8') as f:
        data = json.load(f)
    for item in data:
        nombre = item.get('nombre', '')
        precio = item.get('precio_unitario', 0)
        codigo = item.get('codigo', '')
        proveedor = item.get('proveedor', '')
        fecha = item.get('fecha', datetime.now().isoformat())
        if not nombre or precio <= 0:
            continue
        row = {
            'item': nombre,
            'unidad': 'unidad',
            'valor_unitario': precio,
            'fuente': 'MERCADO_PUBLICO',
            'moneda': 'CLP',
            'idempotency_key': f'mp_{codigo}_{nombre[:30]}',
            'created_at': fecha
        }
        try:
            db.table('precios_serviu').upsert(row, on_conflict='idempotency_key').execute()
            nuevos += 1
        except Exception as e:
            print(f'⚠️ Error con {nombre}: {e}')
print(f'✅ {nuevos} nuevos precios insertados.')
"
echo "✅ Completado - $(date '+%Y-%m-%d %H:%M:%S')"
SCRIPT_EOF

chmod +x scrapers/ejecutar_mercado_diario.sh
echo "✅ Script diario creado en scrapers/ejecutar_mercado_diario.sh"

# 4. Configurar cron (con la línea correcta, sin errores)
echo "⏰ Configurando cron..."
CRON_LINE="0 6 * * * cd /home/ibar/Proyectos/DepaFix && ./scrapers/ejecutar_mercado_diario.sh >> logs/mercado_diario.log 2>&1"
(crontab -l 2>/dev/null | grep -v "ejecutar_mercado_diario" ; echo "$CRON_LINE") | crontab -
if [ $? -eq 0 ]; then
    echo "✅ Cron configurado: $CRON_LINE"
else
    echo "❌ Error al configurar cron. Agrega manualmente:"
    echo "$CRON_LINE"
fi

# 5. Resumen final
echo ""
echo "📊 Resumen de precios en Supabase:"
python3 -c "
from core.db_manager import db
result = db.table('precios_serviu').select('fuente, count', count='exact').group_by('fuente').execute()
print(f'Total registros: {result.count}')
for row in result.data:
    print(f'  - {row.get(\"fuente\", \"sin_fuente\")}: {row.get(\"count\", 0)}')
"

echo ""
echo "✅ ¡Todo listo! El scraper se ejecutará todos los días a las 6 AM."
echo "📝 Logs en: logs/mercado_diario.log"
