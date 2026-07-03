#!/bin/bash
DB_PATH="$HOME/presupuestos.db"
LISTA="productos.txt"

while IFS='|' read -r url categoria; do
    [[ -z "$url" ]] && continue
    echo "Analizando [$categoria] en: $url"
    
    precio=$(python3 extractor_v2.py "$url")
    
    if [ $? -eq 0 ] && [ -n "$precio" ]; then
        nombre=$(echo "$url" | awk -F'/' '{print $(NF-0)}')
        sqlite3 "$DB_PATH" "INSERT INTO tarifas (nombre, costo_por_m2, categoria) VALUES ('$nombre', $precio, '$categoria') ON CONFLICT(nombre) DO UPDATE SET costo_por_m2 = $precio, categoria = '$categoria';"
        echo " -> ¡Round ganado! Precio: $precio"
    else
        echo " -> Fallo técnico en este producto."
    fi
    sleep 3
done < "$LISTA"
