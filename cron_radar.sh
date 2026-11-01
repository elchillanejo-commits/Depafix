#!/usr/bin/env bash
set -u

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$BASE_DIR/venv"
LOG_DIR="$BASE_DIR/logs"
FECHA="$(date '+%Y-%m-%d_%H-%M-%S')"
ARCHIVO_LOG="$LOG_DIR/trabajo_nocturno_${FECHA}.log"

URLS=(
    "https://www.aceitesdelvalle.com"
    "https://www.vinasanpedro.cl"
    "https://www.covap.es"
    "https://www.lechepascual.es"
    "https://www.dulcesol.com"
)

mkdir -p "$LOG_DIR"
cd "$BASE_DIR" || exit 1

if [[ ! -f "$VENV_DIR/bin/activate" ]]; then
    printf 'ERROR: no existe el entorno virtual %s\n' "$VENV_DIR/bin/activate" >&2
    exit 1
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

printf 'INICIO: %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" > "$ARCHIVO_LOG"

python3 -u radar_pymes.py "${URLS[@]}" >> "$ARCHIVO_LOG" 2>&1
ESTADO=$?

EXITOSAS=$(grep -c '^EXITOSA:' "$ARCHIVO_LOG" || true)
FALLIDAS=$(grep -c '^FALLIDA:' "$ARCHIVO_LOG" || true)

printf 'FIN fecha=%s estado %s exitosas=%s fallidas=%s\n' \
    "$(date '+%Y-%m-%d %H:%M:%S')" "$ESTADO" "$EXITOSAS" "$FALLIDAS" >> "$ARCHIVO_LOG"

printf 'Radar finalizado: estado=%s exitosas=%s fallidas=%s log=%s\n' \
    "$ESTADO" "$EXITOSAS" "$FALLIDAS" "$ARCHIVO_LOG"

exit "$ESTADO"
