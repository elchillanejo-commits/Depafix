"""inventory_probe.py — SKUs bajo mínimo + desviación precio SERViu + concentración."""
from __future__ import annotations

import json
import logging
import os
from decimal import Decimal

from dotenv import load_dotenv
from supabase import create_client

from ceo.state import registrar_health

load_dotenv()
log = logging.getLogger(__name__)

UF_REF_2026_CLP = Decimal("39779.29")
UMBRAL_DESVIACION_PRECIO = 0.30
UMBRAL_CONCENTRACION_VALOR = 0.60


def _estado_stock(stock: int, stock_min: int) -> str:
    if stock == 0:
        return "critico"
    if stock < stock_min:
        return "bajo"
    if stock > stock_min * 5:
        return "sobre"
    return "ok"


def _detectar_desviaciones_precio(skus: list[dict]) -> list[dict]:
    """precio_clp vs precio_serviu_uf * UF. Solo sobreprecio."""
    out = []
    for s in skus:
        puf = s.get("precio_serviu_uf")
        pclp = s.get("precio_clp")
        if not puf or not pclp:
            continue
        ref = Decimal(str(puf)) * UF_REF_2026_CLP
        if ref <= 0:
            continue
        actual = Decimal(str(pclp))
        pct = float((actual - ref) / ref)
        if pct > UMBRAL_DESVIACION_PRECIO:
            out.append({
                "sku": s.get("sku"),
                "nombre": str(s.get("nombre", ""))[:40],
                "pct": round(pct * 100, 1),
                "precio_clp": int(actual),
                "serviu_clp": int(ref),
            })
    return out


def _detectar_concentracion_valor(skus: list[dict]) -> dict | None:
    valor_por_sku = []
    for s in skus:
        v = int(s.get("precio_clp") or 0) * int(s.get("stock") or 0)
        if v > 0:
            valor_por_sku.append((s.get("sku"), v))
    if not valor_por_sku:
        return None
    total = sum(v for _, v in valor_por_sku)
    if total == 0:
        return None
    top_sku, top_val = max(valor_por_sku, key=lambda x: x[1])
    pct = top_val / total
    if pct > UMBRAL_CONCENTRACION_VALOR:
        return {"sku": top_sku, "pct": round(pct * 100, 1),
                "valor": top_val, "total": total}
    return None


def inventory_probe_worker(params: dict | None = None) -> dict:
    try:
        client = create_client(
            os.environ["SUPABASE_URL"],
            os.environ["SUPABASE_SERVICE_ROLE_KEY"],
        )
        skus = (client.table("inventario_real")
                .select("sku,nombre,stock,stock_min,precio_clp,"
                        "categoria,codigo_serviu,precio_serviu_uf")
                .execute()).data or []

        if not skus:
            registrar_health(client, "inventory", "real", "warn", None,
                             {"total_skus": 0, "motivo": "tabla_vacia"})
            return {"ok": True, "total_skus": 0, "status": "warn"}

        criticos = [s for s in skus if _estado_stock(s["stock"], s["stock_min"]) == "critico"]
        bajos    = [s for s in skus if _estado_stock(s["stock"], s["stock_min"]) == "bajo"]
        desv     = _detectar_desviaciones_precio(skus)
        conc     = _detectar_concentracion_valor(skus)

        status = "ok"
        if bajos or desv or conc:
            status = "warn"
        if criticos:
            status = "fail"

        payload = {
            "total_skus": len(skus),
            "n_criticos": len(criticos),
            "n_bajos": len(bajos),
            "n_desviaciones_precio": len(desv),
            "concentracion": conc,
            "detalle_criticos": [{"sku": s["sku"], "stock": s["stock"],
                                  "stock_min": s["stock_min"]} for s in criticos[:5]],
            "detalle_desviaciones": desv[:3],
        }
        registrar_health(client, "inventory", "real", status, None, payload)
        return {"ok": True, "total_skus": len(skus), "status": status,
                "n_criticos": len(criticos), "n_bajos": len(bajos),
                "n_desv_precio": len(desv)}
    except Exception as e:
        log.exception("inventory_probe falló")
        return {"ok": False, "error": str(e)[:200]}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(json.dumps(inventory_probe_worker({}), indent=2, ensure_ascii=False, default=str))
