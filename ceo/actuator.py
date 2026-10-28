"""actuator.py — Ejecuta acciones whitelisted del CEO.

Fail-open. Hysteresis por target/24h. Flag ACTUATOR_ENABLED (default 0 = dry_run).
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any

from ceo.notifier import notificar_telegram

if TYPE_CHECKING:
    from ceo.diagnostician import DiagResult

log = logging.getLogger(__name__)

UMBRAL_CONFIANZA = 0.6

ACTION_WHITELIST = {
    "systemctl_restart", "task_rerun", "bot_pausar",
    "notificar_humano", "health_rerun",
}

HYSTERESIS_LIMITS = {
    "systemctl_restart": 2,
    "bot_pausar": 1,
    "task_rerun": 5,
}

CEO_URL = os.environ.get("CEO_URL", "https://depafix-ceo-production.up.railway.app")


def _actuator_enabled() -> bool:
    return os.environ.get("ACTUATOR_ENABLED", "0") == "1"


def _registrar(client: Any, decision_id: int | None, accion: str,
               target: str, resultado: str, payload: dict | None = None) -> int | None:
    """Registra acción en ceo_actions. Retorna id de la fila o None."""
    try:
        resp = client.table("ceo_actions").insert({
            "decision_id": decision_id,
            "accion": accion,
            "target": target,
            "resultado": resultado,
            "payload": payload or {},
        }).execute()
        rows = resp.data or []
        return rows[0].get("id") if rows else None
    except Exception as e:
        log.warning("registrar acción falló: %s", e)
        return None


def _actualizar_resultado(client: Any, action_id: int | None,
                          resultado: str, payload: dict | None = None) -> None:
    if not action_id:
        return
    try:
        update = {"resultado": resultado}
        if payload:
            update["payload"] = payload
        client.table("ceo_actions").update(update).eq("id", action_id).execute()
    except Exception as e:
        log.warning("actualizar resultado falló: %s", e)


def _contar_acciones_24h(client: Any, accion: str, target: str) -> int:
    try:
        corte = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
        resp = (
            client.table("ceo_actions")
            .select("id", count="exact")
            .eq("accion", accion)
            .eq("target", target)
            .eq("resultado", "ok")
            .gte("ts", corte)
            .execute()
        )
        return int(getattr(resp, "count", None) or 0)
    except Exception:
        return 0


COOLDOWN_HORAS = 4


def _ya_notificado(client: Any, accion: str, target: str) -> bool:
    """True si ya se notificó esa (accion, target) en las últimas 4h."""
    if accion != "notificar_humano":
        return False
    try:
        from datetime import datetime, timedelta, timezone
        corte = (datetime.now(timezone.utc) - timedelta(hours=COOLDOWN_HORAS)).isoformat()
        resp = (client.table("ceo_actions")
                .select("id", count="exact")
                .eq("accion", accion)
                .eq("resultado", "ok")
                .gte("ts", corte)
                .execute())
        return int(getattr(resp, "count", None) or 0) > 0
    except Exception:
        return False


def _check_kill_switch(client: Any, accion: str, target: str,
                       payload: dict | None = None) -> tuple[bool, str]:
    """Kill-switch: bloquea si >= 3 acciones ok en últimos 60 min por (accion, target).
    Auto-desbloqueo silencioso tras 6h sin nuevos disparos. Fail-open."""
    try:
        ahora = datetime.now(timezone.utc)
        corte_60min = (ahora - timedelta(minutes=60)).isoformat()
        corte_6h = (ahora - timedelta(hours=6)).isoformat()

        # Contar ok recientes (60 min)
        resp = (
            client.table("ceo_actions")
            .select("id", count="exact")
            .eq("accion", accion).eq("target", target)
            .eq("resultado", "ok")
            .gte("ts", corte_60min)
            .execute()
        )
        n_ok = int(getattr(resp, "count", None) or 0)

        if n_ok < 3:
            return (False, "ok")

        # Contar kill_switch en 6h (para streak)
        resp2 = (
            client.table("ceo_actions")
            .select("id", count="exact")
            .eq("target", target)
            .eq("resultado", "kill_switch")
            .gte("ts", corte_6h)
            .execute()
        )
        streak = int(getattr(resp2, "count", None) or 0) + 1

        # Registrar el bloqueo
        _registrar(client, None, accion, target, "kill_switch",
                   {**(payload or {}), "n_ok_60min": n_ok, "streak": streak})

        # Notificar
        nivel = "fail" if streak >= 3 else "warn"
        msg = f"🛑 Kill-switch activo: {accion}/{target} — {n_ok} ok en 60min (streak {streak})"
        notificar_telegram(msg, nivel=nivel)

        return (True, f"kill_switch n_ok={n_ok} streak={streak}")
    except Exception as e:
        log.warning("kill-switch fail-open: %s", e)
        return (False, "fail_open")


def _hacer_task_rerun(client: Any, target: str) -> tuple[str, str]:
    """target = task_id. Fuerza proxima_ejecucion = now()."""
    try:
        tid = int(target)
        client.table("ceo_tasks").update({
            "proxima_ejecucion": datetime.now(timezone.utc).isoformat(),
            "estado": "pending",
        }).eq("id", tid).execute()
        return "ok", f"task {tid} reprogramada"
    except Exception as e:
        return "fail", str(e)[:100]


def _hacer_bot_pausar(client: Any, motivo: str) -> tuple[str, str]:
    try:
        client.table("bot_control").insert({
            "pausado": True,
            "motivo": motivo[:200] or "pausa por CEO",
        }).execute()
        return "ok", "bot pausado"
    except Exception as e:
        return "fail", str(e)[:100]


def _hacer_notificar_humano(mensaje: str) -> tuple[str, str]:
    ok = notificar_telegram(mensaje[:500] or "alerta del CEO", nivel="fail")
    return ("ok" if ok else "fail"), ("notificado" if ok else "telegram falló")


def _hacer_health_rerun(client: Any) -> tuple[str, str]:
    try:
        client.table("ceo_tasks").insert({
            "tipo": "health_probe",
            "parametros": {},
            "schedule": None,
            "estado": "pending",
            "proxima_ejecucion": datetime.now(timezone.utc).isoformat(),
        }).execute()
        return "ok", "health_probe agendado"
    except Exception as e:
        return "fail", str(e)[:100]


def _hacer_systemctl_restart(target: str) -> tuple[str, str]:
    # Desde Railway NO hay SSH al Vostro. Se marca skip local.
    return "skip_local", f"restart de {target} requiere Vostro (pendiente F14)"


def ejecutar_accion(
    client: Any,
    diag: DiagResult,
    *,
    decision_id: int | None = None,
    dry_run: bool | None = None,
) -> dict:
    """Ejecuta la acción sugerida por un diagnóstico. Fail-open."""
    if not diag.ok or diag.diagnosis is None:
        log.error("Diagnóstico falló: %s", diag.motivo)
        return {"ok": False, "resultado": "diagnostico_fallido",
                "motivo": diag.motivo}

    dx = diag.diagnosis
    accion_original = dx.accion_sugerida
    confianza = dx.confianza
    forzada = dx.requiere_humano or confianza < UMBRAL_CONFIANZA
    accion = "notificar_humano" if forzada else accion_original
    target = (dx.target or "").strip()

    payload_diag = {
        "diagnostico": dx.model_dump(),
        "diag_ok": diag.ok,
        "motivo": diag.motivo,
        "accion_original": accion_original,
        "forzada": forzada,
        "requiere_humano": dx.requiere_humano,
        "confianza": confianza,
        "cached": diag.cached,
        "knowledge_core_usado": diag.knowledge_core_usado,
        "target_original": dx.target,
    }

    if accion == "ninguna":
        motivo = dx.diagnostico
        payload = {
            **payload_diag,
            "motivo": motivo,
            "motivo_diagnostico": diag.motivo,
            "sin_accion": True,
        }
        _registrar(client, decision_id, accion, target, "ok", payload)
        return {"ok": True, "resultado": "ok", "accion": accion,
                "target": target, "motivo": motivo, "sin_accion": True}

    if accion not in ACTION_WHITELIST:
        _registrar(client, decision_id, accion, target,
                   "rechazada_whitelist", payload_diag)
        return {"ok": False, "resultado": "rechazada_whitelist",
                "accion": accion, "target": target}

    # Validar target (evita inyección en logs/SQL). Acepta unicode.
    import re as _re
    if target and not _re.match(r"^[\w\.\-\s:/áéíóúÁÉÍÓÚñÑ,;()]{0,500}$", target):
        _registrar(client, decision_id, accion, target,
                   "target_invalido", payload_diag)
        return {"ok": False, "resultado": "target_invalido",
                "accion": accion, "target": target}

    # Si notificar_humano no trae target, usar el diagnóstico como mensaje.
    if accion == "notificar_humano" and not target:
        target = _re.sub(r"[^\w\.\-\s:/áéíóúÁÉÍÓÚñÑ,;()]", "",
                         dx.diagnostico or "")[:500].strip()
        if not target:
            target = "fallo detectado"

    # Actuator flag: si no está habilitado, siempre dry_run
    if dry_run is None:
        dry_run = not _actuator_enabled()

    # Hysteresis
    limite = HYSTERESIS_LIMITS.get(accion)
    if limite is not None:
        usadas = _contar_acciones_24h(client, accion, target)
        if usadas >= limite:
            _registrar(client, decision_id, accion, target, "skip_hysteresis",
                       {**payload_diag, "usadas_24h": usadas, "limite": limite})
            return {"ok": False, "resultado": "skip_hysteresis",
                    "accion": accion, "target": target,
                    "usadas_24h": usadas}

    if dry_run:
        _registrar(client, decision_id, accion, target, "dry_run",
                   payload_diag)
        return {"ok": True, "resultado": "dry_run",
                "accion": accion, "target": target, "dry_run": True}

    # Cooldown: no repetir notificar_humano si ya se hizo en 4h
    if _ya_notificado(client, accion, target):
        _registrar(client, decision_id, accion, target, "skip_cooldown",
                   {**payload_diag,
                    "razon": f"ya notificado en últimas {COOLDOWN_HORAS}h"})
        return {"ok": True, "resultado": "skip_cooldown",
                "accion": accion, "target": target}

    # Kill-switch: bloquea si hubo demasiadas acciones recientes
    bloqueado, motivo_ks = _check_kill_switch(client, accion, target, payload_diag)
    if bloqueado:
        return {"ok": False, "resultado": "kill_switch",
                "accion": accion, "target": target, "motivo": motivo_ks}

    # Registrar pending ANTES de ejecutar (audit trail garantizado)
    action_id = _registrar(client, decision_id, accion, target, "pending",
                           {**payload_diag, "target": target})
    if action_id is None:
        # No se pudo crear el audit trail. Fail-safe: NO ejecutar.
        log.warning("no se pudo registrar pending, abortando acción")
        return {"ok": False, "resultado": "error_audit_trail",
                "accion": accion, "target": target}

    # Ejecutar
    if accion == "task_rerun":
        res, msg = _hacer_task_rerun(client, target)
    elif accion == "bot_pausar":
        res, msg = _hacer_bot_pausar(client, target)
    elif accion == "notificar_humano":
        res, msg = _hacer_notificar_humano(target)
    elif accion == "health_rerun":
        res, msg = _hacer_health_rerun(client)
    elif accion == "systemctl_restart":
        res, msg = _hacer_systemctl_restart(target)
    else:
        res, msg = "rechazada_whitelist", "no implementada"

    _actualizar_resultado(client, action_id, res,
                          {**payload_diag, "mensaje": msg, "target": target})
    return {"ok": res == "ok", "resultado": res, "accion": accion,
            "target": target, "mensaje": msg, "action_id": action_id}
