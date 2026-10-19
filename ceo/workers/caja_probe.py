"""caja_probe.py — Balance de caja de obra + cruce vs precios SERVIU 2026.

FIX 2026-10-14 (v3):
- Desviación SERVIU DESHABILITADA hasta migrar caja_obra con columnas
  cantidad/unidad/codigo_apu_normalizado.
- 'cuadre_diario' es saldo neto del día, NO descuadre contable. Fail
  solo si absurdo (>10M CLP); warn si >3M CLP.
- _detectar_desviaciones_serviu sin abs(): solo sobrecosto, ahorro no
  es desviación.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from dotenv import load_dotenv
from supabase import create_client

from ceo.state import registrar_health

load_dotenv()
log = logging.getLogger(__name__)

UF_REF_2026_CLP = Decimal("39779.29")
UMBRAL_CUADRE_FAIL_CLP = 10_000_000   # absurdo: más que ingreso mensual
UMBRAL_CUADRE_WARN_CLP = 3_000_000    # atípico: 3x promedio diario
UMBRAL_DESVIACION = 0.30
UMBRAL_CONCENTRACION = 0.60
VENTANA_DIAS = 30


def _calcular_cuadre_diario(movs: list[dict]) -> dict[str, int]:
    """Retorna {fecha_iso: balance_clp} por día (saldo neto, no descuadre)."""
    por_dia: dict[str, int] = {}
    for m in movs:
        fecha = str(m["fecha"])[:10]
        signo = 1 if m["tipo"] == "ingreso" else -1
        por_dia[fecha] = por_dia.get(fecha, 0) + signo * int(m["monto_clp"])
    return por_dia


def _detectar_desviaciones_serviu(movs: list[dict], precios: dict[str, Decimal]) -> list[dict]:
    """Compara monto_clp vs precio SERVIU * cantidad. Solo egresos con codigo_serviu.

    Requiere columnas cantidad+unidad en caja_obra. Hasta migrar, se llama
    con desviaciones=[] desde el worker. Sin abs(): solo alerta SOBRECOSTO.
    """
    out = []
    for m in movs:
        if m.get("tipo") != "egreso" or not m.get("codigo_serviu"):
            continue
        if m["codigo_serviu"] not in precios:
            continue
        cantidad = m.get("cantidad")
        if not cantidad or float(cantidad) <= 0:
            continue
        precio_uf = precios[m["codigo_serviu"]]
        referencia_clp = precio_uf * UF_REF_2026_CLP * Decimal(str(cantidad))
        if referencia_clp <= 0:
            continue
        actual = Decimal(str(m["monto_clp"]))
        pct = float((actual - referencia_clp) / referencia_clp)
        if pct > UMBRAL_DESVIACION:
            out.append({
                "id": m.get("id"),
                "concepto": str(m.get("concepto", ""))[:40],
                "pct": round(pct * 100, 1),
                "actual": int(actual),
                "serviu": int(referencia_clp),
            })
    return out


def _detectar_concentracion(movs: list[dict]) -> dict | None:
    """Detecta si >60% del egreso total está en una sola categoría."""
    egresos = [m for m in movs if m.get("tipo") == "egreso"]
    if not egresos:
        return None
    total = sum(int(m["monto_clp"]) for m in egresos)
    if total == 0:
        return None
    por_cat: dict[str, int] = {}
    for m in egresos:
        c = m.get("categoria") or "Sin categoría"
        por_cat[c] = por_cat.get(c, 0) + int(m["monto_clp"])
    cat_top, monto_top = max(por_cat.items(), key=lambda x: x[1])
    pct = monto_top / total
    if pct > UMBRAL_CONCENTRACION:
        return {"categoria": cat_top, "pct": round(pct * 100, 1),
                "monto": monto_top, "total": total}
    return None


def caja_probe_worker(params: dict | None = None) -> dict:
    """Balance de caja 30 días + desviaciones SERVIU. Fail-open."""
    try:
        client = create_client(
            os.environ["SUPABASE_URL"],
            os.environ["SUPABASE_SERVICE_ROLE_KEY"],
        )
        corte = (datetime.now(timezone.utc) - timedelta(days=VENTANA_DIAS)).date().isoformat()

        movs = (client.table("caja_obra")
                .select("id,fecha,tipo,monto_clp,categoria,concepto")
                .gte("fecha", corte)
                .execute()).data or []

        precios_rows = (client.table("precios_serviu_2026")
                        .select("codigo_apu,precio_uf")
                        .execute()).data or []
        precios = {p["codigo_apu"]: Decimal(str(p["precio_uf"])) for p in precios_rows}

        cuadre = _calcular_cuadre_diario(movs)
        # TODO migración: reactivar cuando caja_obra tenga
        # cantidad/unidad/codigo_apu_normalizado.
        desviaciones: list[dict] = []
        concentracion = _detectar_concentracion(movs)

        # Saldo neto diario NO es descuadre contable. Fail solo si absurdo.
        status = "ok"
        if desviaciones or concentracion:
            status = "warn"
        if any(abs(v) > UMBRAL_CUADRE_WARN_CLP for v in cuadre.values()):
            status = "warn"
        if any(abs(v) > UMBRAL_CUADRE_FAIL_CLP for v in cuadre.values()):
            status = "fail"

        payload = {
            "total_movs": len(movs),
            "dias_con_movs": len(cuadre),
            "cuadre_min": min(cuadre.values()) if cuadre else 0,
            "cuadre_max": max(cuadre.values()) if cuadre else 0,
            "n_desviaciones_serviu": len(desviaciones),
            "concentracion": concentracion,
            "detalle_desviaciones": desviaciones[:3],
            "desviacion_estado": "deshabilitada_hasta_migracion_schema",
        }
        registrar_health(client, "caja", "obra", status, None, payload)

        return {"ok": True, "total_movs": len(movs),
                "status": status, "n_desviaciones": len(desviaciones),
                "concentracion": bool(concentracion)}
    except Exception as e:
        log.exception("caja_probe falló")
        return {"ok": False, "error": str(e)[:200]}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(json.dumps(caja_probe_worker({}), indent=2, ensure_ascii=False, default=str))
