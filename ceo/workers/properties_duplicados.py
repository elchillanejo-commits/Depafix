"""properties_duplicados.py — Detecta propiedades duplicadas."""
from __future__ import annotations
import logging
import os
from collections import defaultdict
from dotenv import load_dotenv
from supabase import create_client
from ceo.state import registrar_health

load_dotenv()
log = logging.getLogger(__name__)

def properties_duplicados_worker(params: dict | None = None) -> dict:
    """Detecta propiedades duplicadas y las registra en ceo_health."""
    try:
        client = create_client(
            os.environ["SUPABASE_URL"],
            os.environ["SUPABASE_SERVICE_ROLE_KEY"],
        )

        resp = (
            client.table("properties")
            .select("id,titulo,precio_clp,m2,comuna")
            .eq("activa", True)
            .gt("precio_clp", 0)
            .execute()
        )
        props = resp.data or []

        if not props:
            registrar_health(client, "properties", "duplicados", "ok", None, {"total_props": 0})
            return {"ok": True, "total_props": 0, "n_duplicados": 0}

        # Agrupar por: (comuna, round(m2), round(precio_clp/1000))
        grupos = defaultdict(list)
        for p in props:
            c = (p.get("comuna") or "sin_comuna").strip()
            m2 = round(float(p.get("m2") or 0))
            precio_k = round(float(p.get("precio_clp") or 0) / 1000)
            grupos[(c, m2, precio_k)].append(p)

        duplicados = []
        for key, items in grupos.items():
            if len(items) >= 2:
                duplicados.append({
                    "key": str(key),
                    "n": len(items),
                    "ids": [p["id"] for p in items[:5]]
                })

        status = "warn" if duplicados else "ok"
        payload = {
            "total_props": len(props),
            "n_duplicados": len(duplicados),
            "top_duplicados": sorted(duplicados, key=lambda x: x["n"], reverse=True)[:5]
        }
        
        registrar_health(client, "properties", "duplicados", status, None, payload)

        return {"ok": True, "total_props": len(props), "n_duplicados": len(duplicados)}

    except Exception as e:
        log.exception("properties_duplicados falló")
        return {"ok": False, "error": str(e)[:200]}

if __name__ == "__main__":
    import json
    logging.basicConfig(level=logging.INFO)
    print(json.dumps(properties_duplicados_worker({}), indent=2, ensure_ascii=False, default=str))
