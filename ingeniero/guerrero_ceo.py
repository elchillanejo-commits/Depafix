#!/usr/bin/env python3
"""guerrero_ceo.py — Análisis estratégico del ecosistema DepaFix.
Monitorea estado REAL en Supabase + Rails.

Modo: --dry-run (stdout) | normal (append al HILO + Telegram opcional)
"""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Cargar variables de entorno
from dotenv import load_dotenv

env_path = Path.home() / "PROYECTOS/Proyectos/DepaFix/.env"
load_dotenv(dotenv_path=env_path)

from supabase import create_client

ROOT = Path(os.environ.get("DEPA_FIX_ROOT", Path.home() / "PROYECTOS/Proyectos/DepaFix")).expanduser()
PROYECTOS_DIR = Path(os.environ.get("PROYECTOS_DIR", Path.home() / "PROYECTOS/Proyectos")).expanduser()
HILO_PATH = Path(os.environ.get("HILO_PATH", Path.home() / "Documentos/HILO_CONDUCTOR.txt")).expanduser()

HEALTH_LOG = ROOT / "ingeniero/logs/health.log"
TRADING_LOG = ROOT / "logs/trading_systemd.log"
STATE_JSON = ROOT / "ingeniero/state.json"

WINDOW_H = 24
TS_RE = re.compile(r"(\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2})")

# === REGLAS DE NEGOCIO ===
RULES = {
    "trade_expected_cycles": 288,  # 24h / 5min = 288
    "trade_min_signals": 20,       # umbral realista
    "trade_max_gaps_hour": 3,      # máximo de gaps por hora
    "persistencia_min_pct": 90,    # % señales con confluencia persistida
    "health_window_hours": 24,
    "health_errors_max": 5,        # > 5 errores en 24h → crítico
    "dirty_projects_max": 3,
    "stale_project_days": 30,
    "stale_project_warn_days": 14,
    "hilo_stale_hours": 48,
    "no_git_max": 5,
}

def get_supabase():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        return None
    return create_client(url, key)

def _tail(path, n=2000):
    if not path.exists():
        return []
    try:
        with path.open("rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            block = min(size, 300_000)
            f.seek(max(0, size - block))
            data = f.read().decode("utf-8", errors="replace")
        return data.splitlines()[-n:]
    except OSError:
        return []

def _run(cmd, timeout=10):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
        return r.stdout if r.returncode == 0 else None
    except Exception:
        return None

def collect_health():
    # 1. Intentar Supabase
    sb = get_supabase()
    if sb:
        try:
            cutoff = (datetime.now(timezone.utc) - timedelta(hours=RULES["health_window_hours"])).isoformat()
            # Asumimos tabla 'health_checks' con columnas 'timestamp' y 'status' ('OK', 'WARN', 'ERROR')
            # O simplemente contar errores en el campo 'status'
            res = sb.table("health_checks").select("timestamp,status").gte("timestamp", cutoff).execute()
            
            ok = warn = err = 0
            for r in res.data:
                if r["status"] == "OK": ok += 1
                elif r["status"] == "WARN": warn += 1
                elif r["status"] == "ERROR": err += 1
            return {"ok": ok, "warn": warn, "err": err}
        except Exception as e:
            print(f"DEBUG: Supabase health failed: {e}", file=sys.stderr)
            pass

    # 2. Fallback local
    lines = _tail(HEALTH_LOG)
    if not lines: return None
    cutoff = datetime.now(timezone.utc) - timedelta(hours=RULES["health_window_hours"])
    ok = warn = err = 0
    for ln in lines:
        try:
            data = json.loads(ln)
            ts = datetime.fromisoformat(data.get("timestamp", "").replace("Z", "+00:00"))
            if ts.tzinfo is None: ts = ts.replace(tzinfo=timezone.utc)
            if ts < cutoff: continue
            for c in data.get("checks", []):
                if c.get("ok"): ok += 1
                else: err += 1
        except: continue
    return {"ok": ok, "warn": warn, "err": err}

def collect_trading():
    # 1. Intentar Supabase
    sb = get_supabase()
    if sb:
        try:
            cutoff = (datetime.now(timezone.utc) - timedelta(hours=RULES["health_window_hours"])).isoformat()
            # Asumimos tabla 'operaciones_ejecutadas'
            # Necesitamos: timestamp, tipo (COMPRA/VENTA/ESPERA), confluencia_detalle
            res = sb.table("operaciones_ejecutadas").select("created_at,tipo,confluencia_detalle").gte("created_at", cutoff).execute()
            
            data = res.data
            total = len(data)
            compras = len([r for r in data if r["tipo"] == "COMPRA"])
            ventas = len([r for r in data if r["tipo"] == "VENTA"])
            esperas = len([r for r in data if r["tipo"] == "ESPERA"])
            confluencia = len([r for r in data if r.get("confluencia_detalle") is not None])
            
            # Persistencia: % señales con confluencia_detalle NOT NULL
            persistencia_pct = (confluencia / total * 100) if total > 0 else 0
            
            # Gaps: buscar intervalos > 10 min
            # Ordenar por tiempo
            times = sorted([datetime.fromisoformat(r["created_at"].replace("Z", "+00:00")) for r in data])
            gaps = 0
            for i in range(1, len(times)):
                if (times[i] - times[i-1]).total_seconds() > 600:
                    gaps += 1
            
            return {
                "ciclos": total, # Asumimos 1 registro = 1 ciclo exitoso
                "senales": total, 
                "compras": compras,
                "ventas": ventas,
                "esperas": esperas,
                "persistencia_pct": persistencia_pct,
                "gaps": gaps,
                "errores": 0 # TODO: ver si hay tabla de errores o filtrar
            }
        except Exception as e:
            print(f"DEBUG: Supabase trading failed: {e}", file=sys.stderr)
            pass

    # 2. Fallback local
    lines = _tail(TRADING_LOG)
    if not lines: return None
    cutoff = datetime.now(timezone.utc) - timedelta(hours=WINDOW_H)
    ciclos = senales = errores = 0
    for ln in lines:
        # Reutilizar parsing local existente... (simplificado)
        if "Ciclo completado" in ln: ciclos += 1
        if "Señal registrada" in ln: senales += 1
        if "[ERROR]" in ln: errores += 1
    return {"ciclos": ciclos, "senales": senales, "errores": errores}

def collect_projects():
    if not PROYECTOS_DIR.is_dir():
        return []
    out = []
    for entry in sorted(PROYECTOS_DIR.iterdir()):
        if not entry.is_dir() or entry.name.startswith("."):
            continue
        info = {"name": entry.name, "is_git": (entry / ".git").exists(),
                "commits_24h": 0, "last_ts": None, "dirty": False,
                "days_since": None}
        if not info["is_git"]:
            out.append(info)
            continue
        last = _run(["git", "-C", str(entry), "log", "-1", "--format=%cI"])
        if last:
            info["last_ts"] = last.strip()
            try:
                lt = datetime.fromisoformat(info["last_ts"].replace("Z", "+00:00"))
                if lt.tzinfo is None:
                    lt = lt.replace(tzinfo=timezone.utc)
                info["days_since"] = (datetime.now(timezone.utc) - lt).days
            except ValueError:
                pass
        cnt = _run(["git", "-C", str(entry), "log", "--since=24 hours ago", "--oneline"])
        info["commits_24h"] = len([l for l in (cnt or "").splitlines() if l.strip()])
        st = _run(["git", "-C", str(entry), "status", "--porcelain"])
        info["dirty"] = bool((st or "").strip())
        out.append(info)
    return out

def analyze(health, trading, projects):
    """Aplica reglas y produce {critico: [], importante: [], sugerencia: []}."""
    critico, importante, sugerencia = [], [], []

    # --- Health ---
    if health:
        if health["err"] > RULES["health_errors_max"]:
            critico.append(
                f"Salud: {health['err']} checks fallidos en 24h "
                f"(umbral {RULES['health_errors_max']})"
            )

    # --- Trading ---
    if trading:
        # Ajuste para el nuevo formato de trading
        if trading.get("ciclos", 0) < RULES["trade_expected_cycles"]:
            critico.append(
                f"Trading: solo {trading['ciclos']} ciclos en 24h "
                f"(esperado ≥{RULES['trade_expected_cycles']})"
            )
        if trading.get("persistencia_pct", 100) < RULES["persistencia_min_pct"]:
            importante.append(
                f"Trading: persistencia baja ({trading['persistencia_pct']}%). "
                f"Menor al {RULES['persistencia_min_pct']}%"
            )
        if trading.get("gaps", 0) > RULES["trade_max_gaps_hour"]:
            importante.append(
                f"Trading: demasiados gaps en señalización ({trading['gaps']} en 24h)"
            )

    # --- Monorepo ---
    if projects:
        dirty = [p for p in projects if p["is_git"] and p["dirty"]]
        if len(dirty) > RULES["dirty_projects_max"]:
            importante.append(
                f"{len(dirty)} repos con cambios sin commitear: "
                f"{', '.join(p['name'] for p in dirty[:3])}"
            )

        no_git = [p for p in projects if not p["is_git"]]
        if len(no_git) > RULES["no_git_max"]:
            sugerencia.append(
                f"{len(no_git)}/{len(projects)} proyectos sin git. "
                "Priorizar: los que tengan código activo"
            )

        stale = [p for p in projects if p["days_since"] is not None
                 and p["days_since"] > RULES["stale_project_days"]]
        for p in stale[:3]:
            importante.append(
                f"`{p['name']}` sin commits hace {p['days_since']}d — "
                "¿archivar o reactivar?"
            )

        warn_stale = [p for p in projects if p["days_since"] is not None
                      and RULES["stale_project_warn_days"] <= p["days_since"] <= RULES["stale_project_days"]]
        for p in warn_stale[:3]:
            sugerencia.append(
                f"`{p['name']}` {p['days_since']}d sin actividad — vigilar"
            )

    # --- HILO ---
    if HILO_PATH.exists():
        mtime = datetime.fromtimestamp(HILO_PATH.stat().st_mtime)
        hours = (datetime.now() - mtime).total_seconds() / 3600
        if hours > RULES["hilo_stale_hours"]:
            importante.append(
                f"HILO sin actualización hace {int(hours)}h "
                f"(umbral {RULES['hilo_stale_hours']}h)"
            )

    return {"critico": critico, "importante": importante, "sugerencia": sugerencia}

def format_guerrero(health, trading, projects, analysis):
    now = datetime.now()
    L = []
    a = L.append
    a("")
    a(f"## ⚔️ GUERRERO CEO — {now:%Y-%m-%d %H:%M}")
    a("")

    if analysis["critico"]:
        a("### 🚨 CRÍTICO (acción inmediata)")
        for item in analysis["critico"]: a(f"- {item}")
        a("")

    if analysis["importante"]:
        a("### ⚠️ IMPORTANTE (esta semana)")
        for item in analysis["importante"]: a(f"- {item}")
        a("")

    if analysis["sugerencia"]:
        a("### 💡 SUGERENCIAS")
        for item in analysis["sugerencia"]: a(f"- {item}")
        a("")

    a("### 📊 MÉTRICAS 24h")
    if health:
        a(f"- Health: {health['ok']} ok · {health['err']} err")
    if trading:
        # Formato actualizado
        a(f"- Trading: {trading['ciclos']} ciclos · Persistencia: {trading.get('persistencia_pct', 0):.1f}%")
        a(f"  - Compras: {trading.get('compras', 0)} · Ventas: {trading.get('ventas', 0)} · Espera: {trading.get('esperas', 0)}")
    if projects:
        git_proj = [p for p in projects if p["is_git"]]
        a(f"- Monorepo: {len(projects)} proyectos · {len(git_proj)} con git · "
          f"{len([p for p in git_proj if p['dirty']])} dirty")
    a("")

    if not analysis["critico"] and not analysis["importante"]:
        a("**Veredicto: 🟢 Todo en orden.** Seguir plan actual.")
    elif analysis["critico"]:
        a(f"**Veredicto: 🔴 {len(analysis['critico'])} críticos.** Priorizar antes de avanzar.")
    else:
        a(f"**Veredicto: 🟡 {len(analysis['importante'])} pendientes.** Sin urgencia crítica.")
    a("")
    a(f"_Guerrero CEO · {now:%H:%M:%S}_")
    a("")
    return "\n".join(L)

def append_hilo(report):
    HILO_PATH.parent.mkdir(parents=True, exist_ok=True)
    with HILO_PATH.open("a", encoding="utf-8") as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        try:
            f.write(report)
            if not report.endswith("\n"): f.write("\n")
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    health = collect_health()
    trading = collect_trading()
    projects = collect_projects()
    analysis = analyze(health, trading, projects)
    report = format_guerrero(health, trading, projects, analysis)

    if args.dry_run:
        print(report)
        return 0

    append_hilo(report)
    print(f"✅ Guerrero CEO → {HILO_PATH}", file=sys.stderr)
    return 0

if __name__ == "__main__":
    sys.exit(main())
PYEOF
