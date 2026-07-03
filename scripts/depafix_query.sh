#!/bin/bash
DB_PATH="$HOME/presupuestos.db"

if [ -z "$1" ]; then
    echo "Uso: ./consultar.sh [categoria]"
    echo "Ejemplo: ./consultar.sh pintura"
    exit 1
fi

echo "--- Reporte de Precios: $1 ---"
sqlite3 -column -header "$DB_PATH" "SELECT nombre, costo_por_m2 FROM tarifas WHERE categoria = '$1' ORDER BY costo_por_m2 ASC;"
