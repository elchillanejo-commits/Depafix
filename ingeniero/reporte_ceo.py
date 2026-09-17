#!/usr/bin/env python3
"""reporte_ceo.py — Reporte ejecutivo diario del monorepo DepaFix.

Lee health.log, trading_systemd.log, y git logs de ~/PROYECTOS/Proyectos/*
Escribe append atómico al HILO. Modo --dry-run para test.
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

ROOT = Path(os.environ.get("DEPA_FIX_ROOT", Path.home() / "PROYECTOS/Proyectos/DepaFix")).expanduser()
PROYECTOS_DIR = Path(os.environ.get("PROYECTOS_DIR", Path.home() / "PROYECTOS/Proyectos")).expanduser()
HILO_PATH = Path(os.environ.get("HILO_PATH", Path.home() / "Documentos/HILO_CONDUCTOR.txt")).expanduser()

HEALTH_LOG = ROOT / "ingeniero/logs/health.log"
TRADING_LOG = ROOT / "logs/trading_systemd.log"

WINDOW = timedelta(hours=24)
TS_RE = re.compile(r"(\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2})")


def _parse_ts(s):
    m = TS_RE.search(s)
    if not m:
        return None
    try:
        return datetime.fromisoformat(m.group(1).replace(" ", "T"))
    except ValueError:
        return None


def _tail(path, n=2000):
    if not path.exists():
        return []
    try:
        with path.open("rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            block = min(size, 200_000)
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
    lines = _tail(HEALTH_LOG)
    if not lines:
        return None
    cutoff = datetime.now() - WINDOW
    ok = warn = err = 0
    last_supabase = None
    for ln in lines:
        ts = _parse_ts(ln)
        if ts and ts < cutoff:
            continue
        if '"ok": true' in ln:
            ok += 1
        elif '"ok": false' in ln:
            warn += 1
        if "supabase_db" in ln:
            try:
                data = json.loads(ln)
                for c in data.get("checks", []):
                    if c.get("name") == "supabase_db":
                        last_supabase = c
            except (json.JSONDecodeError, AttributeError):
                pass
    return {"ok": ok, "warn": warn, "err": err, "last_supabase": last_supabase}


def collect_trading():
    lines = _tail(TRADING_LOG)
    if not lines:
        return None
    cutoff = datetime.now() - WINDOW
    ciclos = senales = errores = 0
    ultimo = None
    for ln in lines:
        ts = _parse_ts(ln)
        if ts and ts < cutoff:
            continue
        if "Ciclo completado" in ln:
            ciclos += 1
            ultimo = ln[:19]
        if "Señal registrada" in ln:
            senales += 1
        if "[ERROR]" in ln:
            errores += 1
    return {"ciclos": ciclos, "senales": senales, "errores": errores, "ultimo": ultimo}


def collect_projects():
    if not PROYECTOS_DIR.is_dir():
        return []
    out = []
    for entry in sorted(PROYECTOS_DIR.iterdir()):
        if not entry.is_dir() or entry.name.startswith("."):
            continue
        info = {"name": entry.name, "is_git": (entry / ".git").exists(),
                "commits_24h": 0, "last_ts": None, "last_subject": None, "dirty": False}
        if not info["is_git"]:
            out.append(info)
            continue
        last = _run(["git", "-C", str(entry), "log", "-1", "--format=%cI|%s"])
        if last:
            parts = last.strip().split("|", 1)
            info["last_ts"] = parts[0]
            info["last_subject"] = parts[1] if len(parts) > 1 else ""
        cnt = _run(["git", "-C", str(entry), "log", "--since=24 hours ago", "--oneline"])
        info["commits_24h"] = len([l for l in (cnt or "").splitlines() if l.strip()])
        st = _run(["git", "-C", str(entry), "status", "--porcelain"])
        info["dirty"] = bool((st or "").strip())
        out.append(info)
    return out


def format_report(health, trading, projects):
    now = datetime.now()
    L = []
    a = L.append
    a("")
    a(f"## 📊 REPORTE CEO — {now:%Y-%m-%d %H:%M}")
    a("")
    a("### 1. Salud (últimas 24h)")
    if health:
        a(f"- Checks: {health['ok']} ok · {health['warn']} warn · {health['err']} err")
        sb = health.get("last_supabase")
        if sb:
            a(f"- Supabase: `{sb.get('output', 'N/A')[:80]}`")
    else:
        a("- (no disponible)")
    a("")
    a("### 2. Trading (últimas 24h)")
    if trading:
        a(f"- Ciclos completados: **{trading['ciclos']}**")
        a(f"- Señales generadas: **{trading['senales']}**")
        a(f"- Errores: {trading['errores']}")
        if trading.get("ultimo"):
            a(f"- Último ciclo: {trading['ultimo']}")
    else:
        a("- (no disponible)")
    a("")
    a(f"### 3. Monorepo ({len(projects)} proyectos)")
    if projects:
        con_act = [p for p in projects if p["commits_24h"] > 0]
        a(f"- Con actividad 24h: **{len(con_act)}/{len(projects)}**")
        for p in projects[:15]:
            if not p["is_git"]:
                a(f"- `{p['name']}` — sin git")
                continue
            flags = []
            if p["commits_24h"]:
                flags.append(f"**{p['commits_24h']} commits**")
            if p["dirty"]:
                flags.append("⚠ dirty")
            fs = f"  ({', '.join(flags)})" if flags else ""
            ts = (p["last_ts"] or "")[:16]
            a(f"- `{p['name']}` — {ts}: {(p['last_subject'] or '')[:50]}{fs}")
    a("")
    a(f"_Generado por reporte_ceo.py a las {now:%H:%M:%S}_")
    a("")
    return "\n".join(L)


def append_hilo(report):
    HILO_PATH.parent.mkdir(parents=True, exist_ok=True)
    with HILO_PATH.open("a", encoding="utf-8") as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        try:
            f.write(report)
            if not report.endswith("\n"):
                f.write("\n")
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    health = collect_health()
    trading = collect_trading()
    projects = collect_projects()

    report = format_report(health, trading, projects)

    if args.dry_run:
        print(report)
        return 0

    append_hilo(report)
    print(f"✅ Reporte anexado a {HILO_PATH}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
