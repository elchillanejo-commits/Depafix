#!/usr/bin/env python3
import json
import os
import subprocess
import sys
import datetime
import urllib.request
import urllib.error

# Configuration
LOG_FILE = "ingeniero/logs/health.log"
MAX_LOG_SIZE = 10 * 1024 * 1024 # 10MB

def rotate_log():
    if os.path.exists(LOG_FILE) and os.path.getsize(LOG_FILE) > MAX_LOG_SIZE:
        os.truncate(LOG_FILE, 0)

def run_command(cmd):
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
        return result.stdout.strip(), result.returncode
    except Exception as e:
        return str(e), 1

def check_supabase():
    """Chequea frescura de operaciones_ejecutadas (no velas_cripto).
    Arregla 3 bugs: imports faltantes, tz-aware, campo correcto."""
    try:
        from dotenv import load_dotenv
        load_dotenv()
        from supabase import create_client

        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        if not url or not key:
            return {"name": "supabase_db", "ok": False,
                    "output": "faltan SUPABASE_URL o SUPABASE_SERVICE_ROLE_KEY"}

        client = create_client(url, key)
        data = (client.table("operaciones_ejecutadas")
                .select("timestamp")
                .order("timestamp", desc=True)
                .limit(1)
                .execute().data)

        if not data:
            return {"name": "supabase_db", "ok": False, "output": "sin operaciones"}

        raw = data[0].get("timestamp")
        if not raw:
            return {"name": "supabase_db", "ok": False, "output": "sin timestamp"}

        import datetime as dt_mod
        dt = dt_mod.datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=dt_mod.timezone.utc)

        now = dt_mod.datetime.now(dt_mod.timezone.utc)
        delta = (now - dt).total_seconds()
        if delta > 1800:
            return {"name": "supabase_db", "ok": False,
                    "output": f"stale: {dt.isoformat()} ({int(delta)}s)"}
        return {"name": "supabase_db", "ok": True, "output": f"OK: {dt.isoformat()}"}
    except Exception as e:
        return {"name": "supabase_db", "ok": False, "output": f"{type(e).__name__}: {e}"}


def load_env():
    if os.path.exists(".env"):
        with open(".env") as f:
            for line in f:
                if "=" in line:
                    key, value = line.split("=", 1)
                    os.environ[key.strip()] = value.strip()

def main():
    load_env()
    checks = []
    all_ok = True

    # 1. Systemctl
    out, code = run_command("systemctl --user is-active depafix-trading.service")
    checks.append({"name": "bot_service", "ok": code == 0, "output": out})
    if code != 0: all_ok = False

    # 2. Docker
    out, code = run_command("docker ps --filter name=core-postgres --format '{{.Status}}'")
    checks.append({"name": "postgres_container", "ok": code == 0 and "Up" in out, "output": out})
    if not (code == 0 and "Up" in out): all_ok = False

    # 3. Supabase
    ok, msg = check_supabase()
    checks.append({"name": "supabase_db", "ok": ok, "output": msg})
    if not ok: all_ok = False

    # 4. Logs
    out, _ = run_command("tail -100 logs/trading_systemd.log | grep -c ERROR")
    error_count = int(out) if out.isdigit() else 0
    checks.append({"name": "error_logs", "ok": error_count == 0, "output": f"{error_count} errors found"})
    if error_count > 0: all_ok = False

    # Output
    result = {"timestamp": datetime.datetime.now().isoformat(), "checks": checks}
    print(json.dumps(result))
    
    # Log
    rotate_log()
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(result) + "\n")
        
    sys.exit(0 if all_ok else 1)

if __name__ == "__main__":
    main()
