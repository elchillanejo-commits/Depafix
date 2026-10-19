"""reporter_daily.py — Resumen ejecutivo del CEO (texto plano, sin LLM)."""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from supabase import create_client

from ceo.notifier import notificar_telegram

load_dotenv()
log = logging.getLogger(__name__)


def reporter_daily_worker(params: dict | None = None) -> dict:
    """Resumen 24h a Telegram. Fail-open."""
    try:
        client = create_client(
            os.environ["SUPABASE_URL"],
            os.environ["SUPABASE_SERVICE_ROLE_KEY"],
        )
    except Exception as e:
        log.exception("reporter create_client falló")
        return {"ok": False, "error": str(e)[:150]}

    corte = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()

    try:
        health = (client.table("ceo_health").select("source,status")
                  .gte("ts", corte).execute()).data or []
        health_prod = [h for h in health if not h["source"].startswith("demo_")]
        health_demo = [h for h in health if h["source"].startswith("demo_")]
        decisions = (client.table("ceo_decisions").select("accion_sugerida,cost_usd,modelo")
                     .gte("ts", corte).execute()).data or []
        actions = (client.table("ceo_actions").select("accion,resultado")
                   .gte("ts", corte).execute()).data or []
    except Exception as e:
        log.warning("reporter queries fallaron: %s", e)
        return {"ok": False, "error": str(e)[:150]}

    ok = sum(1 for h in health_prod if h["status"] == "ok")
    warn = sum(1 for h in health_prod if h["status"] == "warn")
    fail = sum(1 for h in health_prod if h["status"] == "fail")
    demo_fails = sum(1 for h in health_demo if h["status"] == "fail")

    costo = sum(float(d.get("cost_usd") or 0) for d in decisions)
    modelos = {}
    for d in decisions:
        modelos[d["modelo"]] = modelos.get(d["modelo"], 0) + 1

    acc_ok = sum(1 for a in actions if a["resultado"] == "ok")
    acc_dry = sum(1 for a in actions if a["resultado"] == "dry_run")
    acc_skip = sum(1 for a in actions if a["resultado"].startswith("skip") or a["resultado"].startswith("rechaz"))

    lineas = [
        "📊 CEO Informático — Resumen 24h",
        f"Health: {ok} ok / {warn} warn / {fail} fail",
        f"Diagnósticos: {len(decisions)} llamadas, ${costo:.4f}",
        f"Acciones: {acc_ok} ok / {acc_dry} dry / {acc_skip} skip",
    ]
    if demo_fails:
        lineas.append(f"(Demo noise: {demo_fails} fails suppressed)")
    if modelos:
        lineas.append("Modelos: " + ", ".join(f"{k}={v}" for k, v in modelos.items()))
    if fail > 5:
        lineas.append(f"🔴 Atención: {fail} fails en 24h")

    mensaje = "\n".join(lineas)
    notificar_telegram(mensaje, nivel="info")
    log.info("reporter envió: %s", mensaje)

    return {
        "ok": True,
        "resumen": mensaje,
        "health": {"ok": ok, "warn": warn, "fail": fail},
        "costo_usd": round(costo, 4),
        "n_decisiones": len(decisions),
        "n_acciones": len(actions),
    }
