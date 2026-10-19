"""flota_probe.py — Service vencido + rendimiento anómalo + documentos por vencer."""
from __future__ import annotations

import json
import logging
import os
from datetime import date, datetime, timezone

from dotenv import load_dotenv
from supabase import create_client

from ceo.state import registrar_health

load_dotenv()
log = logging.getLogger(__name__)

KM_ALERTA_SERVICE = 500
DIAS_ALERTA_DOC = 30
UMBRAL_RENDIMIENTO = 0.80


def _check_service(v: dict) -> dict | None:
    falta = v["km_proximo_service"] - v["km_actual"]
    if falta <= KM_ALERTA_SERVICE:
        return {"tipo": "service", "falta_km": falta,
                "km_actual": v["km_actual"],
                "km_proximo": v["km_proximo_service"]}
    return None


def _check_documentos(v: dict, hoy: date) -> dict | None:
    dv = v.get("documentos_vencen")
    if not dv:
        return None
    if isinstance(dv, str):
        dv = date.fromisoformat(dv[:10])
    dias = (dv - hoy).days
    if dias <= DIAS_ALERTA_DOC:
        return {"tipo": "documentos", "dias_restantes": dias,
                "vencimiento": dv.isoformat()}
    return None


def _check_rendimiento(v: dict, viajes: list[dict]) -> dict | None:
    recientes = sorted([x for x in viajes if x["patente"] == v["patente"]],
                       key=lambda x: x["fecha"], reverse=True)[:5]
    if not recientes:
        return None
    km_total = sum(float(x["km"]) for x in recientes)
    l_total = sum(float(x["litros"]) for x in recientes)
    if l_total <= 0:
        return None
    r_real = km_total / l_total
    r_esperado = float(v["rendimiento_km_l"])
    if r_esperado <= 0:
        return None
    ratio = r_real / r_esperado
    if ratio < UMBRAL_RENDIMIENTO:
        return {"tipo": "rendimiento",
                "rendimiento_real": round(r_real, 2),
                "rendimiento_esperado": r_esperado,
                "ratio": round(ratio, 2),
                "viajes_analizados": len(recientes)}
    return None


def flota_probe_worker(params: dict | None = None) -> dict:
    try:
        client = create_client(
            os.environ["SUPABASE_URL"],
            os.environ["SUPABASE_SERVICE_ROLE_KEY"],
        )
        vehiculos = (client.table("flota_vehiculos")
                     .select("patente,marca,modelo,km_actual,"
                             "km_proximo_service,rendimiento_km_l,"
                             "documentos_vencen")
                     .execute()).data or []
        viajes = (client.table("viajes")
                  .select("patente,fecha,km,litros")
                  .execute()).data or []

        hoy = datetime.now(timezone.utc).date()
        issues_por_vehiculo: dict[str, list[dict]] = {}
        for v in vehiculos:
            checks = []
            for fn in (
                lambda: _check_service(v),
                lambda: _check_documentos(v, hoy),
                lambda: _check_rendimiento(v, viajes),
            ):
                r = fn()
                if r:
                    checks.append(r)
            if checks:
                issues_por_vehiculo[v["patente"]] = checks

        n_service = sum(1 for ch in issues_por_vehiculo.values()
                        for c in ch if c["tipo"] == "service")
        n_docs = sum(1 for ch in issues_por_vehiculo.values()
                     for c in ch if c["tipo"] == "documentos")
        n_rend = sum(1 for ch in issues_por_vehiculo.values()
                     for c in ch if c["tipo"] == "rendimiento")

        status = "ok"
        if issues_por_vehiculo:
            status = "warn"
        for ch in issues_por_vehiculo.values():
            for c in ch:
                if c["tipo"] == "service" and c["falta_km"] <= 0:
                    status = "fail"

        payload = {
            "total_vehiculos": len(vehiculos),
            "total_viajes": len(viajes),
            "n_con_issues": len(issues_por_vehiculo),
            "n_service": n_service,
            "n_documentos": n_docs,
            "n_rendimiento": n_rend,
            "detalle": issues_por_vehiculo,
        }
        registrar_health(client, "flota", "vehiculos", status, None, payload)
        return {"ok": True, "total_vehiculos": len(vehiculos),
                "status": status, "n_con_issues": len(issues_por_vehiculo),
                "n_service": n_service, "n_docs": n_docs, "n_rend": n_rend}
    except Exception as e:
        log.exception("flota_probe falló")
        return {"ok": False, "error": str(e)[:200]}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(json.dumps(flota_probe_worker({}), indent=2, ensure_ascii=False, default=str))
