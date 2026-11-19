from __future__ import annotations

import json
import logging
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

import pandas as pd

from .config import (
    GEOCODE_BOUNDS,
    GEOCODE_DELAY_SECONDS,
    GEOCODE_USER_AGENT,
)

logger = logging.getLogger(__name__)

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
VIEWBOX = "-70.72,-33.40,-70.60,-33.50"


def _base_address(direccion: str) -> str:
    text = re.sub(r",\s*Depto\..*$", "", direccion, flags=re.IGNORECASE)
    text = re.sub(r",\s*Torre\s+.*$", "", text, flags=re.IGNORECASE)
    text = text.replace("(sin número)", "").strip(" ,")
    return text


def _inside_bounds(lat: float, lon: float) -> bool:
    return (
        GEOCODE_BOUNDS["lat_min"] <= lat <= GEOCODE_BOUNDS["lat_max"]
        and GEOCODE_BOUNDS["lon_min"] <= lon <= GEOCODE_BOUNDS["lon_max"]
    )


def _confidence(item: dict[str, Any], street_only: bool) -> str:
    if street_only:
        return "baja"
    address = item.get("address") or {}
    if address.get("house_number") and item.get("type") in {
        "apartments",
        "house",
        "building",
        "residential",
    }:
        return "alta"
    if item.get("type") in {"apartments", "house", "building", "residential"}:
        return "media"
    return "baja"


def _request(query: str) -> list[dict[str, Any]]:
    params = {
        "q": query,
        "format": "jsonv2",
        "limit": 1,
        "countrycodes": "cl",
        "addressdetails": 1,
        "viewbox": VIEWBOX,
        "bounded": 1,
    }
    url = f"{NOMINATIM_URL}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(url, headers={"User-Agent": GEOCODE_USER_AGENT})
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.load(response)


def _geocode_one(base: str, street_only: bool = False) -> dict[str, Any] | None:
    variants = []
    if not street_only:
        variants = [
            f"{base}, Santiago Centro, Chile",
            f"{base}, Santiago, Chile",
        ]
    else:
        variants = [f"{base}, Santiago Centro, Chile"]

    for index, query in enumerate(variants):
        try:
            results = _request(query)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            logger.warning("Geocodificación falló para %r: %s", query, exc)
            continue
        finally:
            time.sleep(GEOCODE_DELAY_SECONDS)
        if not results:
            continue
        item = results[0]
        try:
            lat = float(item["lat"])
            lon = float(item["lon"])
        except (KeyError, TypeError, ValueError):
            continue
        if not _inside_bounds(lat, lon):
            logger.warning("Resultado fuera de Santiago Centro para %r: %s,%s", query, lat, lon)
            continue
        return {
            "lat": lat,
            "lon": lon,
            "display_name": item.get("display_name", ""),
            "confidence": _confidence(item, street_only),
            "query": query,
            "type": item.get("type", ""),
            "variant": index,
        }
    return None


def geocode_dataframe(
    df: pd.DataFrame,
    cache_path: Path,
    enabled: bool = True,
    max_queries: int | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache: dict[str, Any] = {}
    if cache_path.exists():
        try:
            cache = json.loads(cache_path.read_text())
        except json.JSONDecodeError:
            logger.warning("Cache de geocodificación inválida; se regenera.")
            cache = {}

    unique = (
        df.loc[~df["es_administracion"], ["direccion_normalizada", "calle", "numero"]]
        .drop_duplicates(subset=["direccion_normalizada"])
        .reset_index(drop=True)
    )
    requests_done = 0
    for _, row in unique.iterrows():
        key = row["direccion_normalizada"]
        if key in cache and cache[key].get("lat") is not None:
            continue
        if not enabled:
            continue
        if max_queries is not None and requests_done >= max_queries:
            break
        base = _base_address(key)
        result = _geocode_one(base)
        requests_done += 1
        if result is None and row["numero"]:
            street = _base_address(key).rsplit(" ", 1)[0]
            result = _geocode_one(street, street_only=True)
            requests_done += 1
        if result is not None:
            cache[key] = result
            cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=2))
            logger.info("Geocodificado %s -> %.5f,%.5f", key, result["lat"], result["lon"])
        else:
            logger.warning("Sin coordenadas para %s", key)

    rows = []
    for key, value in cache.items():
        rows.append(
            {
                "direccion_normalizada": key,
                "lat": value.get("lat"),
                "lon": value.get("lon"),
                "geocoding_display_name": value.get("display_name", ""),
                "geocoding_confianza": value.get("confidence", "baja"),
                "geocoding_query": value.get("query", ""),
            }
        )
    coords = pd.DataFrame(rows)
    if coords.empty:
        coords = pd.DataFrame(
            columns=[
                "direccion_normalizada",
                "lat",
                "lon",
                "geocoding_display_name",
                "geocoding_confianza",
                "geocoding_query",
            ]
        )
    merged = df.merge(coords, how="left", on="direccion_normalizada")
    merged["geocodificado"] = merged["lat"].notna() & merged["lon"].notna()
    meta = {
        "cache_path": str(cache_path),
        "solicitudes_realizadas": requests_done,
        "direcciones_unicas": int(len(unique)),
        "geocodificadas": int(merged["geocodificado"].sum()),
        "sin_coordenadas": int((~merged["geocodificado"]).sum()),
    }
    return merged, meta
