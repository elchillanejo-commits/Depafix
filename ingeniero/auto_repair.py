#!/usr/bin/env python3
"""
auto_repair.py — Auto-reparación controlada para DepaFix.
"""
from __future__ import annotations
import json
import logging
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
INGENIERO_DIR = PROJECT_ROOT / "ingeniero"
HEALTH_LOG = INGENIERO_DIR / "logs" / "health.log"
AUTO_REPAIR_LOG = INGENIERO_DIR / "logs" / "auto_repair.log"
STATE_FILE = INGENIERO_DIR / "state.json"
TRADING_SYSTEMD_LOG = PROJECT_ROOT / "logs" / "trading_systemd.log"

ACTION_TIMEOUT_S = 30
MAX_RESTARTS_PER_HOUR = 3

ACTION_MAP = {
    "bot_service": {"type": "restart", "cmd": ["systemctl", "--user", "restart", "depafix-trading.service"], "service": "depafix-trading.service"},
    "systemd_trading": {"type": "restart", "cmd": ["systemctl", "--user", "restart", "depafix-trading.service"], "service": "depafix-trading.service"},
    "postgres_container": {"type": "restart", "cmd": ["docker", "restart", "core-postgres"], "service": "core-postgres"},
    "docker_postgres": {"type": "restart", "cmd": ["docker", "restart", "core-postgres"], "service": "core-postgres"},
    "supabase_db": {"type": "alert", "reason": "servicio externo, no se repara desde aquí"},
    "supabase_ping": {"type": "alert", "reason": "servicio externo, no se repara desde aquí"},
    "error_logs": {"type": "truncate", "path": TRADING_SYSTEMD_LOG},
    "log_errors": {"type": "truncate", "path": TRADING_SYSTEMD_LOG},
    "velas_fresh": {"type": "alert", "reason": "datos de mercado — revisión humana"},
}

FORBIDDEN_BINARIES = {"rm", "git", "curl", "wget", "drop"}


def _setup_logging() -> logging.Logger:
    AUTO_REPAIR_LOG.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("auto_repair")
    logger.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    fh = logging.FileHandler(AUTO_REPAIR_LOG, encoding="utf-8")
    fh.setFormatter(fmt)
    logger.addHandler(fh)
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    logger.addHandler(sh)
    return logger


def read_last_health() -> dict:
    if not HEALTH_LOG.exists():
        raise FileNotFoundError(f"no existe {HEALTH_LOG}")
    last = ""
    with HEALTH_LOG.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                last = line
    if not last:
        raise ValueError(f"{HEALTH_LOG} vacío")
    return json.loads(last)


def load_state() -> dict:
    if not STATE_FILE.exists():
        return {"restarts": {}}
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"restarts": {}}


def save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2), encoding="utf-8")
    tmp.replace(STATE_FILE)


def _prune_old_restarts(timestamps, now):
    cutoff = now - timedelta(hours=1)
    kept = []
    for ts in timestamps:
        try:
            t = datetime.fromisoformat(ts)
        except ValueError:
            continue
        if t >= cutoff:
            kept.append(ts)
    return kept


def can_restart(state, service, now):
    restarts = state.setdefault("restarts", {})
    history = _prune_old_restarts(restarts.get(service, []), now)
    restarts[service] = history
    return len(history) < MAX_RESTARTS_PER_HOUR


def record_restart(state, service, now):
    restarts = state.setdefault("restarts", {})
    restarts.setdefault(service, []).append(now.isoformat())


def _validate_cmd(cmd):
    if not cmd:
        raise ValueError("cmd vacío")
    binary = Path(cmd[0]).name.lower()
    if binary in FORBIDDEN_BINARIES:
        raise PermissionError(f"comando prohibido: {binary}")


def run_restart(cmd):
    _validate_cmd(cmd)
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=ACTION_TIMEOUT_S, check=False)
        out = (proc.stdout or "") + (proc.stderr or "")
        return proc.returncode == 0, out.strip()
    except subprocess.TimeoutExpired:
        return False, f"timeout tras {ACTION_TIMEOUT_S}s"
    except FileNotFoundError as exc:
        return False, f"binario no encontrado: {exc}"
    except Exception as exc:
        return False, f"error inesperado: {exc}"


def run_truncate(path):
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8")
        return True, f"truncado: {path}"
    except Exception as exc:
        return False, f"error truncando {path}: {exc}"


def process_check(check, state, logger, now):
    name = check.get("name", "<sin_nombre>")
    action = ACTION_MAP.get(name)
    if action is None:
        logger.warning(f"check desconocido '{name}' — sin acción (humano)")
        return True
    kind = action["type"]
    if kind == "alert":
        logger.warning(f"[ALERTA] {name}: {action['reason']}")
        return True
    if kind == "truncate":
        ok, out = run_truncate(action["path"])
        logger.info(f"[TRUNCATE] {name} → ok={ok} {out}")
        return True
    if kind == "restart":
        service = action["service"]
        if not can_restart(state, service, now):
            logger.error(f"[ESCALAR] {service} excedió {MAX_RESTARTS_PER_HOUR} restarts/h")
            return False
        ok, out = run_restart(action["cmd"])
        if ok:
            record_restart(state, service, now)
            logger.info(f"[RESTART] {service} ok — {out or 'sin salida'}")
        else:
            logger.error(f"[RESTART] {service} FALLÓ — {out}")
        return True
    logger.error(f"tipo de acción desconocido: {kind}")
    return True


def main() -> int:
    logger = _setup_logging()
    now = datetime.now(timezone.utc)
    try:
        health = read_last_health()
    except Exception as exc:
        logger.error(f"no se pudo leer health.log: {exc}")
        return 1
    if health.get("all_ok") is True:
        logger.info("health OK — nada que reparar")
        return 0
    checks = health.get("checks") or []
    failed = [c for c in checks if not c.get("ok")]
    if not failed:
        logger.warning("all_ok=False pero sin checks fallidos — JSON inconsistente")
        return 0
    logger.info(f"checks fallidos: {[c.get('name') for c in failed]}")
    state = load_state()
    escalate = False
    for check in failed:
        try:
            if not process_check(check, state, logger, now):
                escalate = True
                break
        except Exception as exc:
            logger.error(f"error procesando '{check.get('name')}': {exc}")
            escalate = True
            break
    try:
        save_state(state)
    except Exception as exc:
        logger.error(f"no se pudo guardar state.json: {exc}")
        return 1
    return 1 if escalate else 0


if __name__ == "__main__":
    sys.exit(main())
