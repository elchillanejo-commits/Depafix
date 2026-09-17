#!/usr/bin/env python3
"""health_check.py — Chequeos de salud sin Claude. Exit 0 si todo OK."""
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
LOG_FILE = BASE / "ingeniero/logs/health.log"
MAX_LOG_SIZE = 10 * 1024 * 1024  # 10 MB
STALE_MIN = 30  # minutos para considerar stale el bot


def rotate_log():
    if LOG_FILE.exists() and LOG_FILE.stat().st_size > MAX_LOG_SIZE:
        LOG_FILE.write_text("", encoding="utf-8")


def run_cmd(cmd, timeout=10):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return r.returncode == 0, (r.stdout or r.stderr).strip()
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


def check_bot_service():
    ok, out = run_cmd("systemctl --user is-active depafix-trading.service")
    return ok and out == "active", out or "inactive"


def check_postgres():
    ok, out = run_cmd("docker ps --filter name=core-postgres --format '{{.Status}}'")
    return ok and "Up" in out, out or "not running"


def check_supabase():
    """Frescura de operaciones_ejecutadas. El bot escribe cada 5 min."""
    try:
        from dotenv import load_dotenv
        load_dotenv(BASE / ".env")
        from supabase import create_client

        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        if not url or not key:
            return False, "faltan SUPABASE_URL o SUPABASE_SERVICE_ROLE_KEY"

        client = create_client(url, key)
        data = (
            client.table("operaciones_ejecutadas")
            .select("timestamp")
            .order("timestamp", desc=True)
            .limit(1)
            .execute()
            .data
        )
        if not data:
            return False, "sin operaciones_ejecutadas"

        raw = data[0].get("timestamp")
        if not raw:
            return False, "operación sin timestamp"

        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        delta_s = (now - dt).total_seconds()
        if delta_s > STALE_MIN * 60:
            return False, f"stale: {dt.isoformat()} ({int(delta_s)}s)"
        return True, f"OK: {dt.isoformat()}"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


def check_error_logs():
    log = BASE / "logs/trading_systemd.log"
    if not log.exists():
        return False, "log no existe"
    ok, out = run_cmd(f"tail -200 {log} | grep -c ERROR || true")
    try:
        n = int(out.strip() or "0")
    except ValueError:
        n = 0
    return n < 5, f"{n} errores en últimas 200 líneas"


def main():
    rotate_log()
    checks = []

    for name, fn in [
        ("bot_service", check_bot_service),
        ("postgres_container", check_postgres),
        ("supabase_db", check_supabase),
        ("error_logs", check_error_logs),
    ]:
        try:
            ok, msg = fn()
        except Exception as e:
            ok, msg = False, f"{type(e).__name__}: {e}"
        checks.append({"name": name, "ok": ok, "output": msg})

    result = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "all_ok": all(c["ok"] for c in checks),
        "checks": checks,
    }

    print(json.dumps(result, indent=2, ensure_ascii=False))

    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(result, ensure_ascii=False) + "\n")

    sys.exit(0 if result["all_ok"] else 1)


if __name__ == "__main__":
    main()
