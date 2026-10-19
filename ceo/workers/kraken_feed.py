"""
kraken_feed.py — Worker que puebla velas_cripto con datos de Kraken.

Usa la API PÚBLICA de Kraken (sin credenciales).
Escribe con el nombre EXACTO de columnas del schema real:
    par, temporalidad, tiempo, apertura, maximo, minimo, cierre, volumen

Pares cubiertos:
    BTC/USD -> Kraken pair "XBTUSD"
    ETH/USD -> Kraken pair "ETHUSD"
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

import requests
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()
log = logging.getLogger(__name__)

KRAKEN_OHLC = "https://api.kraken.com/0/public/OHLC"

# par_depafix -> (kraken_pair, kraken_result_key)
PARES = {
    "BTC/USD": ("XBTUSD", "XXBTZUSD"),
    "ETH/USD": ("ETHUSD", "XETHZUSD"),
}

TEMPORALIDAD = "1H"
INTERVALO_MIN = 60  # 1H


def kraken_feed_worker(params: dict | None = None) -> dict:
    params = params or {}
    pares = params.get("pares") or list(PARES.keys())
    limite = int(params.get("limite", 100))

    supa_url = os.environ.get("SUPABASE_URL")
    supa_key = (
        os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        or os.environ.get("SUPABASE_KEY")
    )
    if not supa_url or not supa_key:
        return {"ok": False, "error": "faltan credenciales SUPABASE"}

    sb = create_client(supa_url, supa_key)

    total_insertadas = 0
    detalle = {}

    for par_depafix in pares:
        if par_depafix not in PARES:
            detalle[par_depafix] = {"error": "par no soportado"}
            continue

        kraken_pair, result_key = PARES[par_depafix]

        try:
            resp = requests.get(
                KRAKEN_OHLC,
                params={"pair": kraken_pair, "interval": INTERVALO_MIN},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            log.exception("error consultando Kraken %s", par_depafix)
            detalle[par_depafix] = {"error": f"kraken: {e}"}
            continue

        if data.get("error"):
            detalle[par_depafix] = {"error": data["error"]}
            continue

        result = data.get("result", {})
        velas_raw = result.get(result_key) or []
        if not velas_raw:
            # Kraken a veces devuelve el key con formato alternativo
            for k, v in result.items():
                if k != "last" and isinstance(v, list):
                    velas_raw = v
                    break

        if not velas_raw:
            detalle[par_depafix] = {"error": "sin velas en respuesta"}
            continue

        # Kraken: [time, open, high, low, close, vwap, volume, count]
        filas = []
        for v in velas_raw[-limite:]:
            try:
                ts = int(v[0])
                filas.append({
                    "par": par_depafix,
                    "temporalidad": TEMPORALIDAD,
                    "tiempo": datetime.fromtimestamp(ts, tz=timezone.utc).isoformat(),
                    "apertura": float(v[1]),
                    "maximo": float(v[2]),
                    "minimo": float(v[3]),
                    "cierre": float(v[4]),
                    "volumen": float(v[6]),
                })
            except (ValueError, IndexError, TypeError):
                continue

        if not filas:
            detalle[par_depafix] = {"error": "parseo vacio"}
            continue

        try:
            sb.table("velas_cripto").upsert(
                filas,
                on_conflict="par,temporalidad,tiempo",
            ).execute()
            total_insertadas += len(filas)
            detalle[par_depafix] = {"velas": len(filas)}
        except Exception as e:
            log.exception("error upsert velas_cripto %s", par_depafix)
            detalle[par_depafix] = {"error": f"upsert: {e}"}

    return {
        "ok": total_insertadas > 0,
        "velas_insertadas": total_insertadas,
        "detalle": detalle,
    }


if __name__ == "__main__":
    import json
    print(json.dumps(kraken_feed_worker(), indent=2, ensure_ascii=False))
