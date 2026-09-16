#!/bin/bash
# Uso: ./recibir_firmas.sh /ruta/carpeta/firmas_recibidas
FIRMAS_DIR="${1:-$HOME/Descargas/Firmas}"
mkdir -p "$FIRMAS_DIR"
echo "📂 Firmas se guardarán en: $FIRMAS_DIR"
echo "🔄 Moviendo archivos nuevos..."
inotifywait -m "$FIRMAS_DIR" -e create --format "%f" | while read f; do
    echo "📥 Nueva firma: $f"
done
