"""predictor.py — Predicción de fallos antes de que ocurran.

Patrones alineados con datos reales (no hay 'warn' en producción):
  1. fail_recurrente: 3+ fails en últimos 12 ciclos (>=25% fail rate)
  2. fail_consecutivo: 3+ fails seguidos
  3. latencia_alza: latencia sube >30% vs baseline (20 ciclos)

Filtra demo_*. Fail-open. NUNCA dispara actuator (solo alerta).
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from ceo.notifier import notificar_telegram

log = logging.getLogger(__name__)

VENTANA_RECIENTE = 12       # 3h @ 15min
VENTANA_BASELINE = 20       # 5h
UMBRAL_FAIL_RECURRENTE = 3  # >=3 fails en ventana reciente
UMBRAL_FAIL_CONSECUTIVO = 3
UMBRAL_LATENCIA_ALZA = 0.30  # 30% sobre baseline
HYSTERESIS_HORAS = 2


def _fetch_reciente(client: Any, limite: int = 3000) -> list[dict]:
    resp = (
        client.table("ceo_health")
        .select("source,target,status,latency_ms,ts")
        .order("ts", desc=True)
        .limit(limite)
        .execute()
    )
    return resp.data or []


def _agrupar(rows: list[dict]) -> dict[tuple[str, str], list[dict]]:
    out: dict[tuple[str, str], list[dict]] = {}
    for r in rows:
        if r.get("source", "").startswith("demo_"):
            continue
        if r.get("status") == "skip":
            continue
        key = (r["source"], r.get("target") or "global")
        out.setdefault(key, []).append(r)
    return out


def _ya_emitido(client: Any, source: str, target: str, patron: str) -> bool:
    try:
        corte = (datetime.now(timezone.utc) - timedelta(hours=HYSTERESIS_HORAS)).isoformat()
        resp = (
            client.table("ceo_predictions")
            .select("id")
            .eq("source", source).eq("target", target).eq("patron", patron)
            .gte("ts", corte).limit(1).execute()
        )
        return bool(resp.data)
    except Exception:
        return False


def _guardar(client: Any, source: str, target: str, patron: str,
             severidad: str, detalle: str) -> dict:
    data = {"source": source, "target": target, "patron": patron,
            "severidad": severidad, "detalle": detalle}
    try:
        client.table("ceo_predictions").insert(data).execute()
        if severidad == "warn":
            notificar_telegram(f"⚠️ Predicción [{patron}]: {detalle} en {source}/{target}",
                               nivel="warn")
    except Exception as e:
        log.warning("guardar_pred falló: %s", e)
    return data


def predecir(client: Any) -> list[dict]:
    """Analiza ceo_health. Fail-open: retorna [] si algo falla."""
    try:
        rows = _fetch_reciente(client)
        if not rows:
            return []

        grupos = _agrupar(rows)
        predicciones: list[dict] = []

        for (source, target), grupo in grupos.items():
            grupo = grupo[:VENTANA_BASELINE]
            if len(grupo) < 4:
                continue

            recientes = grupo[:VENTANA_RECIENTE]
            statuses = [r["status"] for r in recientes]
            n_fails = statuses.count("fail")

            # Patrón 1: fail_recurrente
            if n_fails >= UMBRAL_FAIL_RECURRENTE:
                if not _ya_emitido(client, source, target, "fail_recurrente"):
                    pred = _guardar(client, source, target, "fail_recurrente", "warn",
                                    f"{n_fails}/{len(statuses)} fails en ventana reciente")
                    predicciones.append(pred)
                continue

            # Patrón 2: fail_consecutivo
            consec = 0
            for st in statuses:
                if st == "fail":
                    consec += 1
                else:
                    break
            if consec >= UMBRAL_FAIL_CONSECUTIVO:
                if not _ya_emitido(client, source, target, "fail_consecutivo"):
                    pred = _guardar(client, source, target, "fail_consecutivo", "warn",
                                    f"{consec} fails consecutivos")
                    predicciones.append(pred)
                continue

            # Patrón 3: latencia_alza (>30% sobre baseline de 20 ciclos)
            lat = [r.get("latency_ms") for r in grupo if r.get("latency_ms") is not None]
            if len(lat) >= 8:
                baseline = sum(lat[5:]) / max(len(lat[5:]), 1)
                reciente_lat = sum(lat[:3]) / max(len(lat[:3]), 1)
                if baseline > 0 and reciente_lat > baseline * (1 + UMBRAL_LATENCIA_ALZA):
                    alza_pct = round((reciente_lat / baseline - 1) * 100, 1)
                    if not _ya_emitido(client, source, target, "latencia_alza"):
                        pred = _guardar(client, source, target, "latencia_alza", "info",
                                        f"Latencia +{alza_pct}% vs baseline ({int(baseline)}ms → {int(reciente_lat)}ms)")
                        predicciones.append(pred)

        return predicciones
    except Exception as e:
        log.warning("predecir falló (fail-open): %s", e)
        return []
