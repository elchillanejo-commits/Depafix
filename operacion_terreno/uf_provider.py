#!/usr/bin/env python3
"""Proveedor diario de UF con caché offline y conectores a APIs."""

from datetime import date, datetime
import json
import os
from decimal import Decimal, ROUND_HALF_UP
import urllib.request
import urllib.error
from pathlib import Path


def obtener_uf_vigente(uf_override=None, cache_path="datos/uf_cache.json"):
    """
    Retorna (uf_decimal, fecha_iso, fuente).

    Lógica en cascada:
    1. uf_override o entorno DEPAFIX_UF_VALOR
    2. Caché diario (fecha de hoy)
    3. Consulta en vivo (MindiCorder -> Findic.cl fallback)
    4. Fallback offline
    """
    # --- Paso 1: override o entorno ---
    if uf_override is not None:
        try:
            return Decimal(str(uf_override)), date.today().isoformat(), "override"
        except Exception:
            pass

    env_val = os.getenv("DEPAFIX_UF_VALOR")
    if env_val is not None:
        try:
            return Decimal(str(env_val)), date.today().isoformat(), "override"
        except Exception:
            pass

    # --- Paso 2: caché diario ---
    cache_file = Path(cache_path)
    if cache_file.exists():
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            cached_fecha = data.get("fecha", "")
            hoy_iso = date.today().isoformat()
            if cached_fecha == hoy_iso:
                uf_decimal = Decimal(str(data["valor"]))
                return uf_decimal, hoy_iso, "cache_diario"
        except Exception:
            pass

    # --- Paso 3: consulta en vivo ---
    urls = [
        "https://mindicador.cl/api/uf",
        "https://findic.cl/api/uf",
    ]

    ultimo_error = None
    for url in urls:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "DepaFix/1.0"})
            with urllib.request.urlopen(req, timeout=3) as resp:
                raw = resp.read().decode("utf-8")
                data = json.loads(raw)
                valor_raw = data["serie"][0]["valor"]
                # Normalizar: el API puede devolver string o number; asegurar Decimal
                uf_decimal = Decimal(str(valor_raw)).quantize(
                    Decimal("1"), rounding=ROUND_HALF_UP
                )
                fecha_hoy = date.today().isoformat()
                # Guardar caché
                cache_file.parent.mkdir(parents=True, exist_ok=True)
                with open(cache_file, "w", encoding="utf-8") as f:
                    json.dump(
                        {"valor": str(uf_decimal), "fecha": fecha_hoy, "fuente": url.split("//")[1]},
                        f,
                    )
                return uf_decimal, fecha_hoy, url.split("//")[1]
        except Exception as e:
            ultimo_error = e
            continue

    # --- Paso 4: fallback offline ---
    if cache_file.exists():
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            uf_decimal = Decimal(str(data["valor"]))
            fecha_cache = data.get("fecha", date.today().isoformat())
            return uf_decimal, fecha_cache, "cache_offline"
        except Exception:
            pass

    # --- Paso 5: seed inicial ---
    seed_val = Decimal("41364.17")
    seed_fecha = "2026-11-19"
    seed_fuente = "seed_2026_11_19"
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump({"valor": str(seed_val), "fecha": seed_fecha, "fuente": seed_fuente}, f)
    return seed_val, seed_fecha, seed_fuente