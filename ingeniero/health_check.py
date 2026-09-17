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
    url = f"{os.environ.get('SUPABASE_URL')}/rest/v1/velas_cripto?select=created_at&limit=1&order=created_at.desc"
    key = os.environ.get('SUPABASE_SERVICE_ROLE_KEY')
    
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json"
    }
    
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=5) as response:
            if response.status != 200:
                return False, f"Status: {response.status}"
            data = json.loads(response.read().decode())
            if not data:
                return False, "No data in velas_cripto"
            
            # Assuming created_at is in ISO format
            last_created_at = datetime.datetime.fromisoformat(data[0]['created_at'].replace('Z', '+00:00'))
            now = datetime.datetime.now(datetime.timezone.utc)
            if (now - last_created_at).total_seconds() > 900:
                return False, f"Stale: {last_created_at}"
            return True, "OK"
    except Exception as e:
        return False, str(e)

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
