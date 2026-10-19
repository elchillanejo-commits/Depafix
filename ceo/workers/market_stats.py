"""market_stats.py — Worker calculate_market_stats"""
from __future__ import annotations
import logging
import os
import statistics
from datetime import datetime, timezone
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()
log = logging.getLogger(__name__)


def calculate_market_stats_worker(params: dict | None = None) -> dict:
    params = params or {}
    tipo_default = params.get("tipo") or "departamento"

    supa_url = os.environ.get("SUPABASE_URL")
    supa_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY")
    if not supa_url or not supa_key:
        return {"ok": False, "error": "faltan credenciales SUPABASE"}

    sb = create_client(supa_url, supa_key)

    q = (
        sb.table("properties")
        .select("comuna,dormitorios,precio_clp,m2,precio_m2")
        .gt("precio_clp", 0)
    )
    if params.get("comuna"):
        q = q.eq("comuna", params["comuna"])

    try:
        r = q.execute()
    except Exception as e:
        log.exception("error consultando properties")
        return {"ok": False, "error": f"query properties: {e}"}

    props = r.data or []
    if not props:
        return {"ok": False, "error": "sin propiedades con precio válido", "total": 0}

    grupos: dict[tuple, list] = {}
    for p in props:
        comuna = (p.get("comuna") or "sin_comuna").strip().lower()
        dorms = int(p.get("dormitorios") or 0)
        grupos.setdefault((comuna, tipo_default, dorms), []).append(p)

    ahora = datetime.now(timezone.utc).isoformat()
    resultados = []
    for (comuna, tipo, dorms), rows in grupos.items():
        precios, precios_m2 = [], []
        for row in rows:
            precio = row.get("precio_clp")
            if not precio:
                continue
            precios.append(int(precio))
            pm2 = row.get("precio_m2")
            if pm2:
                precios_m2.append(int(pm2))
            elif row.get("m2"):
                try:
                    precios_m2.append(int(int(precio) / int(row["m2"])))
                except (ZeroDivisionError, ValueError, TypeError):
                    pass
        if not precios:
            continue
        resultados.append({
            "comuna": comuna,
            "tipo": tipo,
            "dormitorios": dorms,
            "total_propiedades": len(precios),
            "precio_promedio": int(sum(precios) / len(precios)),
            "precio_mediana": int(statistics.median(precios)),
            "precio_m2_promedio": int(sum(precios_m2) / len(precios_m2)) if precios_m2 else None,
            "precio_min": min(precios),
            "precio_max": max(precios),
            "updated_at": ahora,
        })

    if not resultados:
        return {"ok": False, "error": "sin grupos calculables", "total": 0}

    try:
        sb.table("market_stats").upsert(
            resultados, on_conflict="comuna,tipo,dormitorios"
        ).execute()
    except Exception as e:
        log.exception("error upsert market_stats")
        return {"ok": False, "error": f"upsert: {e}", "grupos": len(resultados)}

    return {"ok": True, "grupos": len(resultados), "propiedades_procesadas": len(props)}


if __name__ == "__main__":
    import json
    print(json.dumps(calculate_market_stats_worker(), indent=2, ensure_ascii=False))
