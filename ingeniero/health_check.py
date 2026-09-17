#!/usr/bin/env python3
"""
health_check.py — Ingeniero Informático DepaFix
Chequea el estado del sistema SIN llamar a Claude.
Exit 0 = todo OK. Exit 1 = algún check falló.
Salida: JSON en stdout + append a ingeniero/logs/health.log
"""
import json
import os
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
LOG_FILE = Path(__file__).resolve().parent / "logs" / "health.log"
STALE_MIN = 15  # umbral para detectar data stale

def run(cmd, timeout=10):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return r.returncode == 0, (r.stdout or r.stderr).strip()
    except Exception as e:
        return False, f"EXCEPTION: {e}"

def check_systemd():
    ok, out = run("systemctl --user is-active depafix-trading.service")
    return {"name": "systemd_trading", "ok": ok and out == "active", "output": out}

def check_docker_postgres():
    ok, out = run("docker ps --filter name=core-postgres --format '{{.Status}}'")
    return {"name": "docker_postgres", "ok": ok and "Up" in out, "output": out}

def check_supabase():
    try:
        from dotenv import load_dotenv
        load_dotenv(BASE / ".env")
        from supabase import create_client
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        if not url or not key:
            return {"name": "supabase_ping", "ok": False, "output": "faltan variables SUPABASE_*"}
        client = create_client(url, key)
        r = client.table("velas_cripto").select("tiempo").order("tiempo", desc=True).limit(1).execute()
        return {"name": "supabase_ping", "ok": True, "output": f"velas_cripto last: {r.data[0]['tiempo'] if r.data else 'empty'}"}
    except Exception as e:
        return {"name": "supabase_ping", "ok": False, "output": f"ERROR: {str(e)[:120]}"}

def check_log_errors():
    log = BASE / "logs" / "trading_systemd.log"
    if not log.exists():
        return {"name": "log_errors", "ok": False, "output": "log no existe"}
    ok, out = run(f"tail -200 {log} | grep -c ERROR || true")
    try:
        n = int(out) if out else 0
        return {"name": "log_errors", "ok": n < 5, "output": f"{n} errores en últimas 200 líneas"}
    except Exception:
        return {"name": "log_errors", "ok": True, "output": out[:80]}

def check_velas_fresh():
    try:
        from dotenv import load_dotenv
        load_dotenv(BASE / ".env")
        from supabase import create_client
        client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_ROLE_KEY"))
        r = client.table("velas_cripto").select("tiempo").order("tiempo", desc=True).limit(1).execute()
        if not r.data:
            return {"name": "velas_fresh", "ok": False, "output": "tabla vacía"}
        last = r.data[0]["tiempo"]
        # Parse ISO
        last_dt = datetime.fromisoformat(last.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        age_min = (now - last_dt).total_seconds() / 60
        return {"name": "velas_fresh", "ok": age_min < 120, "output": f"última vela hace {age_min:.0f} min"}
    except Exception as e:
        return {"name": "velas_fresh", "ok": False, "output": f"ERROR: {str(e)[:120]}"}

def main():
    checks = [
        check_systemd(),
        check_docker_postgres(),
        check_supabase(),
        check_log_errors(),
        check_velas_fresh(),
    ]
    all_ok = all(c["ok"] for c in checks)
    result = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "all_ok": all_ok,
        "checks": checks,
    }
    # Stdout
    print(json.dumps(result, indent=2, ensure_ascii=False))
    # Append al log
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    # Rotar si >10MB
    if LOG_FILE.exists() and LOG_FILE.stat().st_size > 10 * 1024 * 1024:
        LOG_FILE.write_text("")
    with LOG_FILE.open("a") as f:
        f.write(json.dumps(result, ensure_ascii=False) + "\n")
    sys.exit(0 if all_ok else 1)

if __name__ == "__main__":
    main()
