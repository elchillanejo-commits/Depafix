#!/bin/bash
DB_PATH="$HOME/otec.db"
ANIO=${1:-$(date +%Y)}

# Consulta SQL
QUERY="SELECT strftime('%m', fecha) as mes, SUM(total) as ganancia 
       FROM presupuestos 
       WHERE strftime('%Y', fecha) = '$ANIO' 
       GROUP BY mes ORDER BY mes ASC;"

DATA=$(sqlite3 "$DB_PATH" "$QUERY")

if [ -z "$DATA" ]; then
    echo "No hay datos para el año $ANIO."
    exit 0
fi

echo "📊 Ganancias (Ingresos) - Año: $ANIO"
echo "------------------------------------"

# Obtener máximo usando bc para manejar decimales de forma segura
MAX_GANANCIA=$(echo "$DATA" | cut -d'|' -f2 | sort -rn | head -n1)

echo "$DATA" | while IFS="|" read -r mes ganancia; do
    # Calcular longitud: (ganancia / max) * 30, usando bc
    LONGITUD=$(echo "scale=0; ($ganancia / $MAX_GANANCIA) * 30 / 1" | bc)
    
    BARRA=$(printf "%${LONGITUD}s" | tr ' ' '█')
    printf "Mes %s: %10.2f | %s\n" "$mes" "$ganancia" "$BARRA"
done
echo "------------------------------------"
