#!/usr/bin/env bash

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$BASE_DIR/logs"
ARCHIVO_LOG="$LOG_DIR/modo_nocturno_$(date '+%Y-%m-%d_%H-%M-%S').log"

mkdir -p "$LOG_DIR"

(
    set -e
    cd "$BASE_DIR"
    source "$BASE_DIR/venv/bin/activate"

    python3 radar_pymes.py \
        "https://example.com" \
        "https://www.python.org" \
        "https://www.wikipedia.org" \
        "https://www.instagram.com/instagram/" \
        "https://www.instagram.com/natgeo/"
) > "$ARCHIVO_LOG" 2>&1
ESTADO=$?

printf 'Proceso nocturno finalizado con estado %s.\n' "$ESTADO" >> "$ARCHIVO_LOG"

# Apagado opcional: descomenta la siguiente línea si quieres apagar el equipo.
# sudo shutdown -h now

exit "$ESTADO"
