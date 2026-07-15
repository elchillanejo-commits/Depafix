#!/bin/bash
# Ejecuta el scraper para múltiples rubros y combina resultados

RUBROS=("Construcción" "Gráfica" "Capacitación" "Publicidad" "Impresión" "Señalética" "Formación" "Cursos" "Obras civiles" "Edificación")
SALIDA="datos/todos_los_rubros_$(date +%Y%m%d_%H%M%S).json"
mkdir -p datos

echo "🚀 Iniciando scraping masivo para ${#RUBROS[@]} rubros..."

for rubro in "${RUBROS[@]}"; do
    echo "🔍 Buscando: $rubro"
    python3 scrapers/mercado_publico.py --rubro "$rubro" --estado adjudicada --limite 15 --salida "datos/temp_${rubro}.json"
    sleep 1
done

# Combinar todos los archivos JSON en uno solo
echo "📦 Combinando resultados..."
echo '{"resultados": [' > "$SALIDA"
first=true
for file in datos/temp_*.json; do
    if [ -f "$file" ] && [ -s "$file" ]; then
        if [ "$first" = true ]; then
            cat "$file" >> "$SALIDA"
            first=false
        else
            echo ',' >> "$SALIDA"
            cat "$file" >> "$SALIDA"
        fi
    fi
    rm -f "$file"
done
echo ']}' >> "$SALIDA"

echo "✅ Resultados combinados guardados en: $SALIDA"
echo "📊 Total de precios extraídos: $(cat "$SALIDA" | grep -o '"precio_unitario"' | wc -l)"
