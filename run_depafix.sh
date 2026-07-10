#!/usr/bin/env bash
#
# run_depafix.sh
# ---------------
# 1. Verifica que el puerto 6543 sea accesible (vía TCP).
# 2. Si no lo es, intenta establecer un túnel SSH.
# 3. Solo si la conexión está confirmada, ejecuta uvicorn api:app.
# 4. Manejo de errores y logs detallados.

set -euo pipefail

# ----------------------------------------------------------------------
# Configuración por defecto
# ----------------------------------------------------------------------
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-6543}"
UVICORN_APP="${UVICORN_APP:-main:app}"      # Módulo FastAPI (con respecto a APP_DIR)
UVICORN_HOST="${UVICORN_HOST:-0.0.0.0}"
UVICORN_PORT="${UVICORN_PORT:-8000}"
APP_DIR="${APP_DIR:-core}"                  # Subdirectorio donde está la aplicación y el venv

# Túnel SSH (solo se usa si el puerto no es accesible)
SSH_TUNNEL_USER="${SSH_TUNNEL_USER:-}"
SSH_TUNNEL_HOST="${SSH_TUNNEL_HOST:-}"
SSH_TUNNEL_PORT="${SSH_TUNNEL_PORT:-22}"
TUNNEL_LOCAL_PORT="${TUNNEL_LOCAL_PORT:-$DB_PORT}"
TUNNEL_REMOTE_PORT="${TUNNEL_REMOTE_PORT:-$DB_PORT}"

TIMEOUT=3
LOG_DIR="$HOME/Proyectos/DepaFix/logs"
LOG_FILE="$LOG_DIR/run_depafix.log"

# ----------------------------------------------------------------------
# Preparar directorio de logs
# ----------------------------------------------------------------------
mkdir -p "$LOG_DIR"

# ----------------------------------------------------------------------
# Funciones de logging
# ----------------------------------------------------------------------
log() {
    local level="$1"
    shift
    local msg="[$(date '+%Y-%m-%d %H:%M:%S')] [$level] $*"
    echo "$msg" | tee -a "$LOG_FILE" >&2
}

log_info()  { log "INFO" "$@"; }
log_warn()  { log "WARN" "$@"; }
log_error() { log "ERROR" "$@"; }

# ----------------------------------------------------------------------
# Limpieza al salir (matar túnel SSH si fue creado)
# ----------------------------------------------------------------------
cleanup() {
    if [[ -n "${TUNNEL_PID:-}" ]] && kill -0 "$TUNNEL_PID" 2>/dev/null; then
        log_info "Cerrando túnel SSH (PID $TUNNEL_PID)..."
        kill "$TUNNEL_PID" 2>/dev/null || true
    fi
}
trap cleanup EXIT

# ----------------------------------------------------------------------
# Verificar dependencias
# ----------------------------------------------------------------------
command -v nc >/dev/null 2>&1 || {
    log_error "'nc' (netcat) no está instalado. Instálalo con: sudo apt install netcat-openbsd"
    exit 1
}
command -v ssh >/dev/null 2>&1 || {
    log_error "'ssh' no está instalado."
    exit 1
}

# ----------------------------------------------------------------------
# 1. Verificar puerto TCP
# ----------------------------------------------------------------------
check_port() {
    local host="$1" port="$2"
    log_info "Verificando $host:$port..."
    if nc -z -w "$TIMEOUT" "$host" "$port"; then
        log_info "Puerto $host:$port está accesible."
        return 0
    else
        log_warn "No se pudo conectar a $host:$port."
        return 1
    fi
}

# ----------------------------------------------------------------------
# 2. Intentar levantar túnel SSH
# ----------------------------------------------------------------------
start_ssh_tunnel() {
    if [[ -z "$SSH_TUNNEL_USER" || -z "$SSH_TUNNEL_HOST" ]]; then
        log_error "Variables SSH_TUNNEL_USER y SSH_TUNNEL_HOST no definidas."
        return 1
    fi

    log_info "Túnel SSH: ${SSH_TUNNEL_USER}@${SSH_TUNNEL_HOST} -L ${TUNNEL_LOCAL_PORT}:localhost:${TUNNEL_REMOTE_PORT}"
    ssh -N -L "${TUNNEL_LOCAL_PORT}:localhost:${TUNNEL_REMOTE_PORT}" \
        -o "ExitOnForwardFailure=yes" \
        -o "ServerAliveInterval=60" \
        -o "StrictHostKeyChecking=accept-new" \
        -p "$SSH_TUNNEL_PORT" \
        "${SSH_TUNNEL_USER}@${SSH_TUNNEL_HOST}" &
    TUNNEL_PID=$!
    log_info "Túnel SSH iniciado en background (PID $TUNNEL_PID). Esperando ${TIMEOUT}s..."
    sleep "$TIMEOUT"
    if kill -0 "$TUNNEL_PID" 2>/dev/null; then
        log_info "Túnel SSH parece estar activo."
        return 0
    else
        log_error "El proceso SSH terminó inesperadamente."
        return 1
    fi
}

# ----------------------------------------------------------------------
# 3. Ejecutar uvicorn
# ----------------------------------------------------------------------
run_uvicorn() {
    log_info "Lanzando uvicorn $UVICORN_APP en $UVICORN_HOST:$UVICORN_PORT..."
    # Ubicarse en el directorio del script
    cd "$(dirname "$0")"
    # Moverse al subdirectorio de la aplicación si está definido
    if [[ -n "${APP_DIR:-}" ]]; then
        cd "$APP_DIR"
    fi
    # Activar entorno virtual si existe
    if [[ -d "venv" ]]; then
        source venv/bin/activate
        log_info "Entorno virtual activado."
    fi
    # Verificar que uvicorn está disponible
    command -v uvicorn >/dev/null 2>&1 || {
        log_error "'uvicorn' no encontrado. Asegúrate de que el entorno virtual esté activado o instálalo con: pip install uvicorn"
        exit 1
    }
    uvicorn "$UVICORN_APP" --host "$UVICORN_HOST" --port "$UVICORN_PORT"
}

# ----------------------------------------------------------------------
# Lógica principal
# ----------------------------------------------------------------------
main() {
    log_info "Iniciando run_depafix.sh"

    if check_port "$DB_HOST" "$DB_PORT"; then
        log_info "Conexión al puerto $DB_PORT confirmada."
    else
        log_warn "Puerto $DB_PORT no accesible, intentando túnel SSH..."
        if ! start_ssh_tunnel; then
            log_error "No se pudo establecer el túnel SSH. Abortando."
            exit 1
        fi
        if ! check_port "localhost" "$TUNNEL_LOCAL_PORT"; then
            log_error "Aún no se puede acceder al puerto $TUNNEL_LOCAL_PORT tras el túnel. Abortando."
            exit 1
        fi
        log_info "Conexión al puerto $TUNNEL_LOCAL_PORT establecida vía túnel SSH."
    fi

    run_uvicorn
}

main "$@"
