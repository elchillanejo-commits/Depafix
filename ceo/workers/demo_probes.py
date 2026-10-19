"""demo_probes.py — 5 workers demo que alimentan ceo_health.

Cada caso escribe 1 fila (source='demo_<caso>', target='global').
status='ok' si todo bien, 'fail' si hay anomalía.
rules_engine los captura igual que sensores reales.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from supabase import create_client

from ceo.state import registrar_health

load_dotenv()
log = logging.getLogger(__name__)

# Umbrales (configurables)
INV_STOCK_BAJO = 0     # stock < stock_min
CAJA_DESCUADRE_MAX = 500
PEDIDO_MAX_MIN = 30
ASISTENCIA_MAX_HORAS = 8


def _probe_inventario(client) -> dict:
    resp = client.table("demo_inventario").select("sku,stock,stock_min").execute()
    rows = resp.data or []
    bajos = [r for r in rows if int(r["stock"]) < int(r["stock_min"])]
    status = "fail" if bajos else "ok"
    payload = {"total_skus": len(rows), "bajos": len(bajos),
               "detalle": [f"{r['sku']}:{r['stock']}/{r['stock_min']}" for r in bajos[:5]]}
    registrar_health(client, "demo_inventario", "global", status, None, payload)
    return {"status": status, "bajos": len(bajos)}


def _probe_caja(client) -> dict:
    hoy = datetime.now(timezone.utc).date().isoformat()
    resp = (client.table("demo_caja").select("tipo,monto")
            .eq("fecha", hoy).execute())
    rows = resp.data or []
    ingresos = sum(float(r["monto"]) for r in rows if r["tipo"] == "ingreso")
    egresos = sum(float(r["monto"]) for r in rows if r["tipo"] == "egreso")
    diferencia = ingresos - egresos
    status = "fail" if abs(diferencia) > CAJA_DESCUADRE_MAX else "ok"
    payload = {"ingresos": ingresos, "egresos": egresos,
               "diferencia": round(diferencia, 2), "n_movs": len(rows)}
    registrar_health(client, "demo_caja", "global", status, None, payload)
    return {"status": status, "diferencia": round(diferencia, 2)}


def _probe_pedidos(client) -> dict:
    corte = (datetime.now(timezone.utc) - timedelta(minutes=PEDIDO_MAX_MIN)).isoformat()
    resp = (client.table("demo_pedidos").select("id,cliente,ts_creado")
            .in_("estado", ["pendiente", "preparando"])
            .lt("ts_creado", corte).execute())
    huerfanos = resp.data or []
    status = "fail" if huerfanos else "ok"
    payload = {"huerfanos": len(huerfanos),
               "detalle": [f"id={r['id']},cli={r['cliente']}" for r in huerfanos[:5]]}
    registrar_health(client, "demo_pedidos", "global", status, None, payload)
    return {"status": status, "huerfanos": len(huerfanos)}


def _probe_asistencia(client) -> dict:
    corte = (datetime.now(timezone.utc) - timedelta(hours=ASISTENCIA_MAX_HORAS)).isoformat()
    resp = (client.table("demo_asistencia")
            .select("empleado,entrada,salida")
            .is_("salida", "null")
            .not_.is_("entrada", "null")
            .lt("entrada", corte).execute())
    sin_salida = resp.data or []
    status = "fail" if sin_salida else "ok"
    payload = {"sin_salida": len(sin_salida),
               "detalle": [r["empleado"] for r in sin_salida[:5]]}
    registrar_health(client, "demo_asistencia", "global", status, None, payload)
    return {"status": status, "sin_salida": len(sin_salida)}


def _probe_vehiculos(client) -> dict:
    resp = client.table("demo_vehiculos").select("patente,km_actual,km_proximo_service").execute()
    rows = resp.data or []
    vencidos = [r for r in rows
                if int(r["km_actual"]) >= int(r["km_proximo_service"])]
    status = "fail" if vencidos else "ok"
    payload = {"total": len(rows), "vencidos": len(vencidos),
               "detalle": [f"{r['patente']}:{r['km_actual']}/{r['km_proximo_service']}"
                           for r in vencidos[:5]]}
    registrar_health(client, "demo_vehiculos", "global", status, None, payload)
    return {"status": status, "vencidos": len(vencidos)}


def demo_probes_worker(params: dict | None = None) -> dict:
    """Corre los 5 probes demo. Fail-open."""
    try:
        client = create_client(
            os.environ["SUPABASE_URL"],
            os.environ["SUPABASE_SERVICE_ROLE_KEY"],
        )
        resultados = {}
        for nombre, fn in [
            ("inventario", _probe_inventario),
            ("caja",       _probe_caja),
            ("pedidos",    _probe_pedidos),
            ("asistencia", _probe_asistencia),
            ("vehiculos",  _probe_vehiculos),
        ]:
            try:
                resultados[nombre] = fn(client)
            except Exception as e:
                log.warning("probe %s falló: %s", nombre, e)
                resultados[nombre] = {"error": str(e)[:100]}
        return {"ok": True, "resultados": resultados}
    except Exception as e:
        log.exception("demo_probes_worker falló")
        return {"ok": False, "error": str(e)[:200]}
