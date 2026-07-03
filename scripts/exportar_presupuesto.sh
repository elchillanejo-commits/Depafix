#!/bin/bash
# Uso: ./exportar_presupuesto.sh <id_presupuesto>

if [ -z "$1" ]; then
    echo "Uso: $0 <id_presupuesto>"
    exit 1
fi

ID=$1
ARCHIVO_JSON="$HOME/depafix/data/presupuestos/presupuesto_${ID}.json"
ARCHIVO_SALIDA="$HOME/depafix/output/presupuesto_${ID}.txt"

mkdir -p ~/depafix/output

if [ ! -f "$ARCHIVO_JSON" ]; then
    echo "Error: No existe el archivo $ARCHIVO_JSON"
    exit 1
fi

# Extraer datos y generar TXT
CLIENTE=$(jq -r '.cliente' "$ARCHIVO_JSON")
TOTAL=$(jq -r '.total' "$ARCHIVO_JSON")

cat <<FINAL > "$ARCHIVO_SALIDA"
--- PRESUPUESTO DEPAFIX ---
Cliente: $CLIENTE
--------------------------
Detalle:
$(jq -r '.items[] | "- \(.descripcion): \(.precio)"' "$ARCHIVO_JSON")
--------------------------
TOTAL: \$$TOTAL
--------------------------
Generado el: $(date +%d-%m-%Y)
FINAL

echo "✅ Presupuesto exportado en: $ARCHIVO_SALIDA"
cat "$ARCHIVO_SALIDA"
