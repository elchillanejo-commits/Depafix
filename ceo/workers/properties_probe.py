"""properties_probe.py — Detecta oportunidades inmobiliarias en properties.

Corre cada hora, agrupa por comuna, detecta:
  - gangas: precio < 50% de la mediana de la comuna
  - outliers: precio > 200% de la mediana
Escribe a ceo_health con source='properties_oportunidad'.
"""
from __future__ import annotations

import logging
import os
import statistics
from datetime import datetime, timezone

from dotenv import load_dotenv
from supabase import create_client

from ceo.state import registrar_health

load_dotenv()
log = logging.getLogger(__name__)

UMBRAL_GANGA = 0.50       # < 50% de la mediana
UMBRAL_OUTLIER = 2.00     # > 200% de la mediana
MIN_PROPS_COMUNA = 5      # mínimo para calcular mediana confiable


def properties_probe_worker(params: dict | None = None) -> dict:
    """Detecta gangas y outliers. Fail-open."""
    try:
        client = create_client(
            os.environ["SUPABASE_URL"],
            os.environ["SUPABASE_SERVICE_ROLE_KEY"],
        )

        resp = (
            client.table("properties")
            .select("id,titulo,precio_clp,dormitorios,m2,comuna")
            .eq("activa", True)
            .gt("precio_clp", 0)
            .limit(2000)
            .execute()
        )
        props = resp.data or []

        if not props:
            registrar_health(client, "properties", "global", "warn",
                             None, {"razon": "sin propiedades activas"})
            return {"ok": True, "total": 0, "razon": "vacio"}

        # Agrupar por comuna
        por_comuna: dict[str, list[dict]] = {}
        for p in props:
            c = (p.get("comuna") or "sin_comuna").strip()
            por_comuna.setdefault(c, []).append(p)

        gangas: list[dict] = []
        outliers: list[dict] = []

        for comuna, items in por_comuna.items():
            if len(items) < MIN_PROPS_COMUNA:
                continue
            precios = [p["precio_clp"] for p in items]
            mediana = statistics.median(precios)

            for p in items:
                if p["precio_clp"] < mediana * UMBRAL_GANGA:
                    gangas.append({
                        "id": p["id"], "titulo": p["titulo"][:40],
                        "comuna": comuna, "precio": p["precio_clp"],
                        "mediana": int(mediana),
                        "pct": round(p["precio_clp"] / mediana * 100, 1),
                    })
                elif p["precio_clp"] > mediana * UMBRAL_OUTLIER:
                    outliers.append({
                        "id": p["id"], "titulo": p["titulo"][:40],
                        "comuna": comuna, "precio": p["precio_clp"],
                        "mediana": int(mediana),
                    })

        status = "fail" if gangas else "ok"
        payload = {
            "total_props": len(props),
            "n_comunas": len(por_comuna),
            "n_gangas": len(gangas),
            "n_outliers": len(outliers),
            "detalle_gangas": gangas[:3],
        }
        registrar_health(client, "properties", "oportunidades", status, None, payload)

        if gangas:
            log.info("PROPERTIES: %d gangas detectadas", len(gangas))

        return {
            "ok": True,
            "total": len(props),
            "n_gangas": len(gangas),
            "n_outliers": len(outliers),
        }

    except Exception as e:
        log.exception("properties_probe falló")
        return {"ok": False, "error": str(e)[:200]}


if __name__ == "__main__":
    import json
    logging.basicConfig(level=logging.INFO)
    print(json.dumps(properties_probe_worker({}), indent=2, ensure_ascii=False, default=str))
