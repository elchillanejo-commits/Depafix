from __future__ import annotations

import math
import re
import urllib.parse
from typing import Any

import pandas as pd

from .config import GOOGLE_MAPS_WAYPOINT_LIMIT

BLOCK_ORDER = {"Bloque 1": 1, "Bloque 2": 2, "Bloque 3": 3, "Sin asignar": 9}
MAX_STOPS_PER_URL = GOOGLE_MAPS_WAYPOINT_LIMIT + 2


def direccion_base(direccion: str) -> str:
    text = re.sub(r",\s*Depto\..*$", "", direccion, flags=re.IGNORECASE)
    text = re.sub(r",\s*Torre\s+.*$", "", text, flags=re.IGNORECASE)
    return text.replace("(sin número)", "").strip(" ,")


def _haversine(a: dict[str, Any], b: dict[str, Any]) -> float:
    lat1, lon1 = math.radians(float(a["lat"])), math.radians(float(a["lon"]))
    lat2, lon2 = math.radians(float(b["lat"])), math.radians(float(b["lon"]))
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * 6371.0 * math.asin(math.sqrt(h))


def _route_distance(route: list[dict[str, Any]]) -> float:
    return sum(_haversine(route[index], route[index + 1]) for index in range(len(route) - 1))


def _nearest_neighbor(stops: list[dict[str, Any]], start_index: int) -> list[dict[str, Any]]:
    remaining = set(range(len(stops)))
    remaining.remove(start_index)
    route = [stops[start_index]]
    while remaining:
        current = route[-1]
        next_index = min(remaining, key=lambda index: _haversine(current, stops[index]))
        route.append(stops[next_index])
        remaining.remove(next_index)
    return route


def _two_opt(route: list[dict[str, Any]]) -> list[dict[str, Any]]:
    improved = True
    best_distance = _route_distance(route)
    while improved:
        improved = False
        for i in range(1, len(route) - 1):
            for j in range(i + 1, len(route)):
                candidate = route[:i] + list(reversed(route[i : j + 1])) + route[j + 1 :]
                candidate_distance = _route_distance(candidate)
                if candidate_distance + 1e-9 < best_distance:
                    route = candidate
                    best_distance = candidate_distance
                    improved = True
    return route


def _optimize_block(stops: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], str]:
    if len(stops) <= 2:
        return stops, "orden plan"
    if not all(stop.get("geocodificado") for stop in stops):
        return sorted(stops, key=lambda item: item["orden_plan"]), "orden plan (sin coordenadas completas)"
    start = min(range(len(stops)), key=lambda index: stops[index]["orden_plan"])
    route = _nearest_neighbor(stops, start)
    route = _two_opt(route)
    return route, "nearest-neighbor + 2-opt"


def _format_stop(stop: dict[str, Any]) -> str:
    lat, lon = stop.get("lat"), stop.get("lon")
    if pd.notna(lat) and pd.notna(lon):
        return f"{float(lat):.6f},{float(lon):.6f}"
    address = stop["direccion_normalizada"]
    address = re.sub(r",\s*Depto\..*$", "", address, flags=re.IGNORECASE)
    address = re.sub(r",\s*Torre\s+.*$", "", address, flags=re.IGNORECASE)
    address = address.replace("(sin número)", "").strip(" ,")
    return f"{address}, Santiago, Chile"


def _build_url(chunk: list[dict[str, Any]]) -> str:
    origin = _format_stop(chunk[0])
    destination = _format_stop(chunk[-1])
    waypoints = [_format_stop(stop) for stop in chunk[1:-1]]
    url = (
        "https://www.google.com/maps/dir/?api=1"
        f"&origin={urllib.parse.quote(origin, safe=',')}"
        f"&destination={urllib.parse.quote(destination, safe=',')}"
        "&travelmode=driving"
    )
    if waypoints:
        url += "&waypoints=" + "|".join(urllib.parse.quote(point, safe=",") for point in waypoints)
    return url


def _segments(stops: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    if not stops:
        return []
    if len(stops) <= MAX_STOPS_PER_URL:
        return [stops]
    segments: list[list[dict[str, Any]]] = []
    start = 0
    while start < len(stops):
        chunk = stops[start : start + MAX_STOPS_PER_URL]
        segments.append(chunk)
        if start + len(chunk) >= len(stops):
            break
        start += len(chunk)
    return segments


def prepare_route_stops(df: pd.DataFrame) -> list[dict[str, Any]]:
    unit_rows = df[(~df["es_administracion"]) & (df["bloque"] != "Sin asignar")].copy()
    if unit_rows.empty:
        return []

    unit_rows["direccion_base"] = unit_rows["direccion_normalizada"].map(direccion_base)
    grouped = []
    for key, group in unit_rows.groupby("direccion_base", sort=False):
        first = group.iloc[0]
        keys = group["id"].astype(str).tolist()
        states = sorted(set(group["estado"].astype(str)))
        priorities = [value for value in group["prioridad_ready_to_rent"] if value in {"A", "B", "C"}]
        priority = min(priorities) if priorities else "No aplica"
        grouped.append(
            {
                "direccion_normalizada": key,
                "bloque": first["bloque"],
                "direccion": key,
                "departamento": first["departamento"],
                "ids": ", ".join(keys),
                "unidades": len(group),
                "estados": " / ".join(states),
                "prioridad": priority,
                "orden_plan": int(group["orden_plan"].min()),
                "lat": first["lat"] if "lat" in group else None,
                "lon": first["lon"] if "lon" in group else None,
                "geocodificado": bool(first.get("geocodificado", False)),
                "geocoding_confianza": first.get("geocoding_confianza", "sin dato"),
                "observaciones": " ".join(dict.fromkeys(value for value in group["observaciones"].dropna() if value)),
            }
        )

    grouped.sort(
        key=lambda item: (
            BLOCK_ORDER.get(item["bloque"], 9),
            item["orden_plan"],
            item["direccion_normalizada"],
        )
    )
    return grouped


def build_routes(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    stops = prepare_route_stops(df)
    if not stops:
        return pd.DataFrame(), df, {"segmentos": 0, "paradas": 0, "metodo": "sin paradas"}

    routes_rows: list[dict[str, Any]] = []
    key_to_segment: dict[str, tuple[str, int, int]] = {}
    for block in ("Bloque 1", "Bloque 2", "Bloque 3", "Sin asignar"):
        block_stops = [stop for stop in stops if stop["bloque"] == block]
        if not block_stops:
            continue
        ordered, method = _optimize_block(block_stops)
        segments = _segments(ordered)
        for index, segment in enumerate(segments):
            label = f"{block.replace('Bloque ', 'B')}{chr(ord('A') + index)}"
            url = _build_url(segment)
            routes_rows.append(
                {
                    "bloque": block,
                    "segmento": label,
                    "paradas": len(segment),
                    "unidades": sum(stop["unidades"] for stop in segment),
                    "primer_parada": segment[0]["direccion"],
                    "ultima_parada": segment[-1]["direccion"],
                    "waypoints": len(segment) - 2 if len(segment) > 2 else 0,
                    "metodo": method,
                    "url": url,
                }
            )
            for order, stop in enumerate(segment, start=1):
                key_to_segment[stop["direccion_normalizada"]] = (label, order, len(segment))

    routes_df = pd.DataFrame(routes_rows)
    df = df.copy()
    df["direccion_base"] = df["direccion_normalizada"].map(direccion_base)
    df["segmento_ruta"] = df["direccion_base"].map(
        lambda key: key_to_segment.get(key, ("", None, None))[0]
    )
    df["parada_ruta"] = df["direccion_base"].map(
        lambda key: key_to_segment.get(key, ("", None, None))[1]
    )
    df["parada_ruta"] = df["parada_ruta"].astype("Int64")
    meta = {
        "segmentos": len(routes_df),
        "paradas": len(stops),
        "unidades": int(sum(stop["unidades"] for stop in stops)),
        "metodo": ", ".join(sorted(set(routes_df["metodo"]))) if not routes_df.empty else "sin rutas",
        "geocodificadas": int(sum(1 for stop in stops if stop["geocodificado"])),
        "sin_coordenadas": int(sum(1 for stop in stops if not stop["geocodificado"])),
    }
    return routes_df, df, meta
