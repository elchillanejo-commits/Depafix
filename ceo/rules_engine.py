"""rules_engine.py — Evalúa 8 reglas duras sobre ceo_health.

Sin LLM. Sin acciones. Solo clasifica: ok / warn / fail.
Fail-open: si Supabase falla, retorna veredicto "unknown".
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

log = logging.getLogger(__name__)

VENTANA_HORAS = 2          # ventana de análisis
MIN_VELAS_NUEVAS = 100     # R4
MAX_CEO_TASKS_VENCIDAS = 100  # R7
UMBRAL_LATENCIA_WARN = 2000   # R2 (ms)
UMBRAL_LATENCIA_FEED = 10000  # R5 (ms)


def _fetch_health(client: Any, horas: int = VENTANA_HORAS) -> list[dict]:
    """Lee ceo_health excluyendo demos. Filtrado en Python (no SQL LIKE)."""
    corte = (datetime.now(timezone.utc) - timedelta(hours=horas)).isoformat()
    resp = (
        client.table("ceo_health")
        .select("source,target,status,latency_ms,ts,payload")
        .gte("ts", corte)
        .order("ts", desc=True)
        .execute()
    )
    rows = resp.data or []
    # Python startswith evita bug de `_` wildcard en SQL LIKE
    return [r for r in rows if not r.get("source", "").startswith("demo_")]


def _por_target(rows: list[dict]) -> dict[tuple[str, str], list[dict]]:
    out: dict[tuple[str, str], list[dict]] = {}
    for r in rows:
        key = (r["source"], r["target"])
        out.setdefault(key, []).append(r)
    return out


def _r1_railway(rows: list[dict], hist: dict) -> dict | None:
    """Falla si railway tuvo 2 fails seguidos (ignora 'skip')."""
    h = [r for r in hist.get(("railway", "services"), []) if r["status"] != "skip"]
    if len(h) >= 2 and all(r["status"] == "fail" for r in h[:2]):
        return {"regla": "R1", "nivel": "fail",
                "motivo": "railway.services fail en 2 ciclos"}
    return None


def _r2_supabase_latencia(rows: list[dict], hist: dict) -> dict | None:
    h = hist.get(("supabase", "core"), [])
    if len(h) >= 3 and all((r.get("latency_ms") or 0) > UMBRAL_LATENCIA_WARN for r in h[:3]):
        return {"regla": "R2", "nivel": "warn",
                "motivo": f"supabase latencia > {UMBRAL_LATENCIA_WARN}ms en 3 ciclos"}
    return None


def _r3_feed(rows: list[dict], hist: dict) -> dict | None:
    """Falla si feed tuvo 2 fails seguidos (ignora 'skip')."""
    h = [r for r in hist.get(("feed", "depafix-ceo"), []) if r["status"] != "skip"]
    if len(h) >= 2 and all(r["status"] == "fail" for r in h[:2]):
        return {"regla": "R3", "nivel": "fail",
                "motivo": "feed.depafix-ceo fail en 2 ciclos"}
    return None


def _r4_velas_nuevas(rows: list[dict], hist: dict) -> dict | None:
    h = hist.get(("supabase", "core"), [])
    if not h:
        return None
    payload = h[0].get("payload") or {}
    filas = payload.get("filas") or {}
    velas = filas.get("velas_cripto")
    if velas is not None and velas < MIN_VELAS_NUEVAS:
        return {"regla": "R4", "nivel": "warn",
                "motivo": f"velas_cripto={velas} < {MIN_VELAS_NUEVAS}"}
    return None


def _r5_feed_latencia(rows: list[dict], hist: dict) -> dict | None:
    h = hist.get(("feed", "depafix-ceo"), [])
    if len(h) >= 2 and all((r.get("latency_ms") or 0) > UMBRAL_LATENCIA_FEED for r in h[:2]):
        return {"regla": "R5", "nivel": "warn",
                "motivo": f"feed latencia > {UMBRAL_LATENCIA_FEED}ms en 2 ciclos"}
    return None


def _r6_railway_offline(rows: list[dict], hist: dict) -> dict | None:
    h = hist.get(("railway", "services"), [])
    if not h:
        return None
    payload = h[0].get("payload") or {}
    offline = payload.get("offline", 0)
    if offline and offline > 0:
        return {"regla": "R6", "nivel": "fail",
                "motivo": f"railway servicios offline={offline}"}
    return None


def _r7_ceo_tasks_vencidas(client: Any) -> dict | None:
    try:
        ahora = datetime.now(timezone.utc).isoformat()
        resp = (
            client.table("ceo_tasks")
            .select("id", count="exact")
            .eq("estado", "pending")
            .lte("proxima_ejecucion", ahora)
            .execute()
        )
        n = getattr(resp, "count", None) or 0
        if n > MAX_CEO_TASKS_VENCIDAS:
            return {"regla": "R7", "nivel": "warn",
                    "motivo": f"ceo_tasks pending vencidas={n}"}
    except Exception as e:
        log.warning("R7 falló: %s", e)
    return None


def _r9_oportunidades(rows: list[dict], hist: dict) -> list[dict]:
    """R9: properties con gangas → fail inmediato (no esperar 2 ciclos)."""
    h = hist.get(("properties", "oportunidades"), [])
    if not h:
        return []
    ultimo = h[0]
    if ultimo.get("status") != "fail":
        return []
    payload = ultimo.get("payload") or {}
    n_gangas = payload.get("n_gangas", 0)
    if n_gangas > 0:
        return [{"regla": "R9", "nivel": "fail",
                 "motivo": f"properties: {n_gangas} gangas detectadas"}]
    return []


def _r10_inventario(rows: list[dict], hist: dict) -> list[dict]:
    """R10: inventory stock en warn/fail → dispara inmediato."""
    h = hist.get(("inventory", "stock"), [])
    if not h:
        return []
    ultimo = h[0]
    status = ultimo.get("status")
    if status not in ("warn", "fail"):
        return []
    payload = ultimo.get("payload") or {}
    bajos = payload.get("bajos_minimo", 0)
    criticos = payload.get("criticos_sin_stock", 0)
    nivel = "fail" if criticos > 0 else "warn"
    return [{"regla": "R10", "nivel": nivel,
             "motivo": f"inventory: {bajos} bajos, {criticos} críticos sin stock"}]


def _r11_caja(rows: list[dict], hist: dict) -> list[dict]:
    """R11: caja_obra en warn/fail → dispara."""
    h = hist.get(("caja", "obra"), [])
    if not h:
        return []
    ultimo = h[0]
    status = ultimo.get("status")
    if status not in ("warn", "fail"):
        return []
    payload = ultimo.get("payload") or {}
    desv = payload.get("n_desviaciones_serviu", 0)
    nivel = "fail" if status == "fail" else "warn"
    return [{"regla": "R11", "nivel": nivel,
             "motivo": f"caja: {desv} desviaciones vs SERVIU"}]


def _r12_flota(rows: list[dict], hist: dict) -> list[dict]:
    """R12: flota con problemas de service, docs o rendimiento."""
    h = hist.get(("flota", "vehiculos"), [])
    if not h:
        return []
    ultimo = h[0]
    status = ultimo.get("status")
    if status not in ("warn", "fail"):
        return []
    payload = ultimo.get("payload") or {}
    sv = len(payload.get("service_vencidos") or [])
    docs = len(payload.get("docs_por_vencer_30d") or [])
    rend = len(payload.get("anomalias_rendimiento") or [])
    nivel = "fail" if (sv > 0 or rend > 0) else "warn"
    return [{"regla": "R12", "nivel": nivel,
             "motivo": f"flota: {sv} service, {docs} docs, {rend} rendimiento"}]


def _r8_fail_consecutivo(rows: list[dict], hist: dict) -> list[dict]:
    """Retorna lista de reglas R8 (una por target con fail consecutivo)."""
    MIN_CICLOS_FAIL = 2
    out = []
    for key, h in hist.items():
        if len(h) >= MIN_CICLOS_FAIL and all(r["status"] == "fail" for r in h[:MIN_CICLOS_FAIL]):
            out.append({"regla": "R8", "nivel": "fail",
                        "motivo": f"{key[0]}.{key[1]} fail en {MIN_CICLOS_FAIL} ciclos"})
    return out


def evaluar_reglas(client: Any) -> dict:
    """Evalúa las 8 reglas. Fail-open."""
    try:
        rows = _fetch_health(client)
    except Exception as e:
        log.warning("fetch ceo_health falló: %s", e)
        return {"veredicto": "unknown", "error": str(e)[:200],
                "reglas_disparadas": [], "metricas": {}}

    hist = _por_target(rows)
    disparadas: list[dict] = []
    for fn in (_r1_railway, _r2_supabase_latencia, _r3_feed, _r4_velas_nuevas,
               _r5_feed_latencia, _r6_railway_offline, _r8_fail_consecutivo,
               _r9_oportunidades, _r10_inventario, _r11_caja, _r12_flota):
        try:
            r = fn(rows, hist)
            if r is None:
                continue
            if isinstance(r, list):
                disparadas.extend(r)
            else:
                disparadas.append(r)
        except Exception as e:
            log.warning("regla falló: %s", e)

    r7 = _r7_ceo_tasks_vencidas(client)
    if r7:
        disparadas.append(r7)

    fails = [d for d in disparadas if d["nivel"] == "fail"]
    warns = [d for d in disparadas if d["nivel"] == "warn"]

    if fails:
        veredicto = "fail"
    elif len(warns) >= 2:
        veredicto = "warn"
    else:
        veredicto = "ok"

    return {
        "veredicto": veredicto,
        "reglas_disparadas": disparadas,
        "metricas": {
            "n_filas_health": len(rows),
            "n_targets": len(hist),
        },
    }


if __name__ == "__main__":
    import json
    import os

    from dotenv import load_dotenv
    from supabase import create_client

    load_dotenv()
    logging.basicConfig(level=logging.INFO)
    c = create_client(os.environ["SUPABASE_URL"],
                      os.environ["SUPABASE_SERVICE_ROLE_KEY"])
    print(json.dumps(evaluar_reglas(c), indent=2, ensure_ascii=False, default=str))
