"""diagnostician.py — Diagnóstico con Claude cuando veredicto == fail.

Fail-open: si Anthropic falla, retorna ok=False sin tocar nada.
Solo se invoca desde rules_evaluator (no como worker independiente).
Cap $2/día + 5 calls/hora. Cache por contexto_hash (2h).
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from anthropic import Anthropic
from pydantic import BaseModel, ConfigDict, Field, ValidationError

log = logging.getLogger(__name__)

MODEL_HAIKU = "claude-haiku-4-5"
MODEL_SONNET = "claude-sonnet-4-6"
MAX_TOKENS = 800
TIMEOUT_S = 30
CACHE_HORAS = 2

MODEL_PRICING = {
    MODEL_HAIKU:  {"input": 1.0,  "output": 5.0},   # $/MTok
    MODEL_SONNET: {"input": 3.0,  "output": 15.0},
}

ACTION_WHITELIST = {
    "systemctl_restart", "task_rerun", "bot_pausar",
    "notificar_humano", "health_rerun",
}

REGLAS_SIMPLES = {"R1", "R3", "R6"}

AccionTipo = Literal[
    "systemctl_restart", "task_rerun", "bot_pausar",
    "notificar_humano", "health_rerun",
]


class AccionDiagnostico(BaseModel):
    """Schema de salida del LLM. Validación estricta."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    diagnostico: str = Field(min_length=5, max_length=500)
    causa_probable: str = Field(default="no determinada", max_length=500)
    accion_sugerida: AccionTipo
    confianza: float = Field(ge=0.0, le=1.0)
    requiere_humano: bool = True

SYSTEM_PROMPT = """Eres el CEO Informático de DepaFix. Recibes datos de fallo del sistema.

REGLAS DE RESPUESTA (críticas):
- Responde con UN OBJETO JSON válido en UNA SOLA LÍNEA.
- NO uses bloques de codigo markdown (triple backtick).
- NO agregues texto antes o después del JSON.
- Escapa saltos de línea como \\n dentro de strings.
- Strings máximo 200 caracteres.

ESQUEMA EXACTO:
{"diagnostico":"explicación breve","causa_probable":"hipótesis técnica","accion_sugerida":"systemctl_restart|task_rerun|bot_pausar|notificar_humano|health_rerun","confianza":0.0,"requiere_humano":false}

Reglas:
- accion_sugerida SOLO una de las 5 opciones.
- Si no estás seguro: confianza < 0.5 y accion_sugerida = "notificar_humano".
- NO inventes datos."""


def _limpiar_json(raw: str) -> str:
    """Limpia fences de markdown y extrae el JSON válido."""
    s = raw.strip()
    # Quitar fences ```json ... ``` o ``` ... ```
    if s.startswith("```"):
        lineas = s.split("\n")
        if lineas and lineas[0].startswith("```"):
            lineas = lineas[1:]
        if lineas and lineas[-1].strip().startswith("```"):
            lineas = lineas[:-1]
        s = "\n".join(lineas).strip()
    # Extraer desde el primer { al último }
    i = s.find("{")
    j = s.rfind("}")
    if i != -1 and j != -1 and j > i:
        return s[i:j+1]
    return s


def _hash_contexto(veredicto: dict) -> str:
    reglas = veredicto.get("reglas_disparadas") or []
    norm = sorted(f"{r.get('regla')}:{r.get('nivel')}" for r in reglas)
    h = hashlib.sha256("|".join(norm).encode()).hexdigest()
    return h[:16]


def _elegir_modelo(veredicto: dict) -> str:
    reglas = [r.get("regla") for r in (veredicto.get("reglas_disparadas") or [])]
    fails = [r for r in veredicto.get("reglas_disparadas", []) if r.get("nivel") == "fail"]
    if len(fails) == 1 and fails[0].get("regla") in REGLAS_SIMPLES:
        return MODEL_HAIKU
    return MODEL_SONNET


def _presupuesto_ok(client: Any) -> tuple[bool, str]:
    try:
        hoy = datetime.now(timezone.utc).date().isoformat()
        hora_actual = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
        resp = (
            client.table("ceo_llm_budget")
            .select("calls_this_hour,cost_today_usd,max_calls_per_hour,max_cost_per_day")
            .eq("day", hoy)
            .order("ts", desc=True)
            .limit(1)
            .execute()
        )
        rows = resp.data or []
        if not rows:
            return True, "sin_registro_previo"
        r = rows[0]
        if float(r.get("cost_today_usd") or 0) >= float(r.get("max_cost_per_day") or 2.0):
            return False, "presupuesto_dia_agotado"
        if int(r.get("calls_this_hour") or 0) >= int(r.get("max_calls_per_hour") or 5):
            return False, "calls_hora_agotadas"
        return True, "ok"
    except Exception as e:
        log.warning("presupuesto_ok falló: %s", e)
        return True, "error_budget_fail_open"


def _buscar_cache(client: Any, contexto_hash: str) -> dict | None:
    try:
        corte = (datetime.now(timezone.utc) - timedelta(hours=CACHE_HORAS)).isoformat()
        resp = (
            client.table("ceo_decisions")
            .select("id,diagnostico,accion_sugerida,confianza,modelo")
            .eq("contexto_hash", contexto_hash)
            .gte("ts", corte)
            .order("ts", desc=True)
            .limit(1)
            .execute()
        )
        rows = resp.data or []
        return rows[0] if rows else None
    except Exception:
        return None


def _contexto_para_llm(client: Any, veredicto: dict) -> str:
    lineas = ["REGLAS DISPARADAS:"]
    for r in veredicto.get("reglas_disparadas", []):
        lineas.append(f"  [{r.get('regla')}/{r.get('nivel')}] {r.get('motivo')}")

    lineas.append("\nULTIMAS METRICAS CEO_HEALTH:")
    try:
        corte = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        resp = (
            client.table("ceo_health")
            .select("source,target,status,latency_ms,ts")
            .gte("ts", corte)
            .order("ts", desc=True)
            .limit(10)
            .execute()
        )
        for r in (resp.data or []):
            lineas.append(
                f"  {r.get('source')}.{r.get('target')}: "
                f"{r.get('status')} ({r.get('latency_ms')}ms)"
            )
    except Exception:
        lineas.append("  (no disponible)")

    return "\n".join(lineas)


def _actualizar_budget(client: Any, modelo: str, costo: float) -> None:
    try:
        hoy = datetime.now(timezone.utc).date().isoformat()
        hora = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0).isoformat()
        resp = (
            client.table("ceo_llm_budget")
            .select("id,calls_this_hour,cost_this_hour_usd,cost_today_usd")
            .eq("day", hoy)
            .eq("hora", hora)
            .limit(1)
            .execute()
        )
        rows = resp.data or []
        if rows:
            r = rows[0]
            client.table("ceo_llm_budget").update({
                "calls_this_hour": int(r.get("calls_this_hour") or 0) + 1,
                "cost_this_hour_usd": float(r.get("cost_this_hour_usd") or 0) + costo,
                "cost_today_usd": float(r.get("cost_today_usd") or 0) + costo,
                "ultima_llamada_ts": datetime.now(timezone.utc).isoformat(),
                "ultima_llamada_motivo": modelo,
            }).eq("id", r["id"]).execute()
        else:
            client.table("ceo_llm_budget").insert({
                "day": hoy,
                "hora": hora,
                "calls_this_hour": 1,
                "cost_this_hour_usd": costo,
                "cost_today_usd": costo,
                "ultima_llamada_ts": datetime.now(timezone.utc).isoformat(),
                "ultima_llamada_motivo": modelo,
            }).execute()
    except Exception as e:
        log.warning("actualizar_budget falló: %s", e)


def diagnosticar_fallo(client: Any, veredicto: dict) -> dict:
    """Diagnostica un fallo con Claude. Fail-open."""
    if (veredicto.get("veredicto") or "").lower() != "fail":
        return {"ok": False, "motivo_skip": "veredicto_no_fail"}

    ok, motivo = _presupuesto_ok(client)
    if not ok:
        log.warning("diagnosticar_fallo skip: %s", motivo)
        return {"ok": False, "motivo_skip": motivo}

    contexto_hash = _hash_contexto(veredicto)

    cached = _buscar_cache(client, contexto_hash)
    if cached:
        return {
            "ok": True, "reusada": True,
            "decision_id": cached.get("id"),
            "diagnostico": cached.get("diagnostico"),
            "accion_sugerida": cached.get("accion_sugerida"),
            "confianza": cached.get("confianza"),
            "costo_usd": 0.0,
            "motivo_skip": "reusada_cache",
        }

    modelo = _elegir_modelo(veredicto)
    contexto = _contexto_para_llm(client, veredicto)

    try:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            return {"ok": False, "motivo_skip": "sin_api_key"}

        ac = Anthropic(api_key=api_key, timeout=TIMEOUT_S)
        msg = ac.messages.create(
            model=modelo,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": contexto}],
        )
        raw = "".join(b.text for b in msg.content if hasattr(b, "text"))
    except Exception as e:
        log.error("Anthropic falló: %s", e)
        return {"ok": False, "motivo_skip": f"anthropic_error: {str(e)[:80]}"}

    raw_limpio = _limpiar_json(raw)
    try:
        parsed = json.loads(raw_limpio)
    except Exception as e:
        log.warning("JSON parse falló: %s | raw=%s", e, raw_limpio[:200])
        parsed = {
            "diagnostico": raw_limpio[:200] or "parse_error",
            "causa_probable": "parse_error",
            "accion_sugerida": "notificar_humano",
            "confianza": 0.0,
            "requiere_humano": True,
        }

    # Validación estricta Pydantic v2 (fail-safe a notificar_humano)
    try:
        accion_validada = AccionDiagnostico(**parsed)
        llm_output = accion_validada.model_dump()
    except ValidationError as ve:
        log.warning("LLM output no validó schema: %s", ve.errors()[:2])
        llm_output = {
            "diagnostico": str(parsed.get("diagnostico", ""))[:500] or "schema invalido",
            "causa_probable": "schema_invalido",
            "accion_sugerida": "notificar_humano",
            "confianza": 0.0,
            "requiere_humano": True,
        }

    in_tok = msg.usage.input_tokens
    out_tok = msg.usage.output_tokens
    precio = MODEL_PRICING[modelo]
    costo = (in_tok / 1e6) * precio["input"] + (out_tok / 1e6) * precio["output"]

    try:
        ins = client.table("ceo_decisions").insert({
            "modelo": modelo,
            "provider": "anthropic",
            "prompt_tokens": in_tok,
            "output_tokens": out_tok,
            "cost_usd": costo,
            "contexto_hash": contexto_hash,
            "regla_disparada": (veredicto.get("reglas_disparadas") or [{}])[0].get("regla"),
            "diagnostico": llm_output.get("diagnostico"),
            "accion_sugerida": llm_output.get("accion_sugerida"),
            "confianza": llm_output.get("confianza"),
            "aplicada": False,
        }).execute()
        decision_id = (ins.data or [{}])[0].get("id")
    except Exception as e:
        log.warning("insert ceo_decisions falló: %s", e)
        decision_id = None

    _actualizar_budget(client, modelo, costo)

    return {
        "ok": True, "reusada": False,
        "decision_id": decision_id,
        "modelo": modelo,
        "diagnostico": llm_output.get("diagnostico"),
        "causa_probable": llm_output.get("causa_probable"),
        "accion_sugerida": llm_output.get("accion_sugerida"),
        "confianza": llm_output.get("confianza"),
        "requiere_humano": llm_output.get("requiere_humano"),
        "costo_usd": round(costo, 6),
        "prompt_tokens": in_tok,
        "output_tokens": out_tok,
    }
