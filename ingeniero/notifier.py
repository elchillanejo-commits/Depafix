#!/usr/bin/env python3
"""notifier.py — Notificaciones Telegram para el Ingeniero DepaFix (S4)."""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(os.environ.get("DEPA_FIX_ROOT", Path.home() / "PROYECTOS/Proyectos/DepaFix")).expanduser()
STATE_PATH = ROOT / "ingeniero/state.json"
LOG_PATH = ROOT / "ingeniero/logs/notifier.log"

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
ENABLED = os.environ.get("TELEGRAM_ENABLED", "0") == "1"

RATE_LIMIT = 10
RATE_WINDOW = timedelta(hours=1)
TIMEOUT = 10
MAX_RETRIES = 2
LEVELS = {"info": 0, "warn": 1, "error": 2}
MIN_LEVEL = "warn"


def _log(msg: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"{ts} [notifier] {msg}"
    print(line, file=sys.stderr, flush=True)
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def _load_state() -> dict:
    if not STATE_PATH.exists():
        return {}
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _save_state(state: dict) -> None:
    try:
        STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = STATE_PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps(state, indent=2), encoding="utf-8")
        tmp.replace(STATE_PATH)
    except OSError as e:
        _log(f"no se pudo guardar state: {e}")


def _recent_sends(state: dict) -> list:
    cutoff = time.time() - RATE_WINDOW.total_seconds()
    out = []
    for t in state.get("telegram_sent", []):
        try:
            v = float(t)
        except (TypeError, ValueError):
            continue
        if v > cutoff:
            out.append(v)
    return out


def _record_send() -> None:
    state = _load_state()
    sends = _recent_sends(state)
    sends.append(time.time())
    state["telegram_sent"] = sends
    _save_state(state)


def send_message(text: str, level: str = "info") -> bool:
    if LEVELS.get(level, 0) < LEVELS[MIN_LEVEL]:
        _log(f"skip level={level} < {MIN_LEVEL}")
        return False
    if len(_recent_sends(_load_state())) >= RATE_LIMIT:
        _log(f"rate-limit alcanzado ({RATE_LIMIT}/h) — descartando")
        return False
    if not ENABLED:
        _log(f"DRY-RUN [{level}] {text[:140]}")
        _record_send()
        return True
    if not (TOKEN and CHAT_ID):
        _log("falta TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_ID")
        return False
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = urllib.parse.urlencode({
        "chat_id": CHAT_ID,
        "text": text[:4000],
        "parse_mode": "Markdown",
        "disable_web_page_preview": "true",
    }).encode()
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with urllib.request.urlopen(url, data=payload, timeout=TIMEOUT) as r:
                if 200 <= r.status < 300:
                    _log(f"enviado [{level}] ({attempt}/{MAX_RETRIES})")
                    _record_send()
                    return True
                _log(f"HTTP {r.status} intento {attempt}")
        except Exception as e:
            _log(f"fallo intento {attempt}/{MAX_RETRIES}: {e}")
        if attempt < MAX_RETRIES:
            time.sleep(1.5 * attempt)
    return False


def notify_check_failure(check_name: str, output: str) -> bool:
    msg = f"🔴 *Check falló:* `{check_name}`\n```\n{output[:500]}\n```"
    return send_message(msg, level="error")


def notify_escalation(service: str, restarts: int) -> bool:
    msg = f"⚠️ *Escalada:* `{service}` reiniciado {restarts} veces"
    return send_message(msg, level="warn")


def notify_daily_summary(report_md: str) -> bool:
    if not report_md.strip():
        return False
    return send_message(f"📊 *Resumen diario*\n{report_md[:3500]}", level="warn")


if __name__ == "__main__":
    os.environ.setdefault("TELEGRAM_ENABLED", "0")
    _log("=== tests notifier.py ===")
    print(f"send_message(info) -> {send_message('test', 'info')}  (esperado False)")
    print(f"send_message(warn) -> {send_message('test warn', 'warn')}  (esperado True)")
    print(f"notify_check_failure -> {notify_check_failure('bot_service', 'inactive')}")
    print(f"notify_escalation -> {notify_escalation('scraper_rm', 3)}")
    print(f"notify_daily_summary -> {notify_daily_summary('# Resumen\nTodo OK')}")
    st = _load_state()
    st["telegram_sent"] = []
    _save_state(st)
    results = [send_message(f"msg {i}", "warn") for i in range(11)]
    ok = sum(results)
    print(f"rate-limit: {ok}/11 aceptados (esperado {RATE_LIMIT})")
    assert ok == RATE_LIMIT, f"esperado {RATE_LIMIT}, obtuve {ok}"
    print("todos los tests OK")
