#!/bin/bash
DB_PATH="$HOME/presupuestos.db"

echo "--- Resumen de Costos por Categoría ---"
sqlite3 -column -header "$DB_PATH" "SELECT categoria, COUNT(*) as cantidad, SUM(costo_por_m2) as total FROM tarifas GROUP BY categoria;"
echo "---------------------------------------"
