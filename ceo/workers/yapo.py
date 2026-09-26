"""yapo.py — Scraper Yapo.cl vía API interna (sin navegador)."""
import asyncio
import json
import logging
import os
import re
import urllib.parse
from datetime import datetime, timezone

import requests
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()
logger = logging.getLogger(__name__)

API_BASE = "https://public-api.yapo.cl/buyers"
HEADERS = {
    "accept": "application/json, text/plain, */*",
    "accept-language": "es-CL,es;q=0.9,en;q=0.8",
    "origin": "https://www.yapo.cl",
    "referer": "https://www.yapo.cl/",
    "user-agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
    ),
    "x-chref": "WEB",
    "x-cmref": "client",
    "x-commerce": "Yapo",
    "x-country": "CL",
    "x-domain": "Buyer",
    "x-rhsref": "www.yapo.cl",
    "x-txref": "fcbbbb37-6f67-4cc0-a39a-367769e7eb3b",
}


async def scrape_yapo_worker(params: dict) -> dict:
    """Scrapea Yapo vía API interna."""
    comunas = params.get("comunas", ["las-condes", "providencia"])
    limite = params.get("limite_por_comuna", 20)
    region_id = params.get("region_id", 15)  # 15 = RM

    client = create_client(
        os.getenv("SUPABASE_URL"),
        os.getenv("SUPABASE_SERVICE_ROLE_KEY"),
    )

    total_nuevas = 0
    total_actualizadas = 0
    por_comuna = {}
    errores = []

    for comuna in comunas:
        try:
            nuevas, actualizadas = await _scrape_comuna(
                client, comuna, region_id, limite
            )
            total_nuevas += nuevas
            total_actualizadas += actualizadas
            por_comuna[comuna] = {"nuevas": nuevas, "actualizadas": actualizadas}
            await asyncio.sleep(2)
        except Exception as e:
            logger.error(f"Error Yapo {comuna}: {e}")
            errores.append({"comuna": comuna, "error": str(e)[:150]})

    return {
        "ok": True,
        "total_nuevas": total_nuevas,
        "total_actualizadas": total_actualizadas,
        "por_comuna": por_comuna,
        "errores": errores,
        "ejecutado": datetime.now(timezone.utc).isoformat(),
    }


async def _scrape_comuna(client, comuna: str, region_id: int, limite: int):
    """Scrapea una comuna. Devuelve (nuevas, actualizadas)."""
    query_obj = {
        "estateType": [1, 2],
        "regionId": region_id,
        "category": [1240],  # arriendo
    }
    query_encoded = urllib.parse.quote(json.dumps(query_obj, separators=(",", ":")))
    orders_encoded = urllib.parse.quote(
        json.dumps({"orderBy": "listTime", "typeOrder": "desc"}, separators=(",", ":"))
    )

    nuevas = 0
    actualizadas = 0
    procesados = 0
    page = 0
    max_pages = 3

    while procesados < limite and page < max_pages:
        url = (
            f"{API_BASE}/search?page={page}&limit=47"
            f"&query={query_encoded}&orders={orders_encoded}"
        )
        try:
            resp = requests.get(url, headers=HEADERS, timeout=20)
            if resp.status_code != 200:
                logger.warning(f"Yapo API HTTP {resp.status_code}")
                break
            data = resp.json()
            ads = data.get("ads", [])
            if not ads:
                break

            logger.info(f"Yapo {comuna} p{page}: {len(ads)} ads")

            for ad in ads[:limite - procesados]:
                prop = _parse_ad(ad, comuna)
                if not prop:
                    continue
                accion = _upsert_property(client, prop)
                if accion == "nueva":
                    nuevas += 1
                elif accion == "actualizada":
                    actualizadas += 1
                procesados += 1

            # Check pagination
            pag = data.get("pagination", {})
            if not pag.get("hasNext"):
                break

            page += 1
            await asyncio.sleep(1.5)
        except Exception as e:
            logger.warning(f"Yapo loop error: {e}")
            break

    return nuevas, actualizadas


def _parse_ad(ad: dict, comuna: str):
    """Parsea un ad de Yapo API."""
    try:
        list_id = ad.get("listId")
        if not list_id:
            return None

        subject = (ad.get("subject") or "").strip()
        if not subject:
            return None

        # Precio: puede venir como {amount, currency, period}
        price_obj = ad.get("price") or {}
        if isinstance(price_obj, dict):
            precio = price_obj.get("amount") or 0
        else:
            precio = float(price_obj or 0)
        if not precio or precio <= 0:
            return None

        # Solo arriendos (filtrar UF vs CLP)
        currency = price_obj.get("currency") if isinstance(price_obj, dict) else "CLP"
        if currency == "UF":
            return None  # ignorar UF por ahora

        # Atributos comunes
        attrs = {}
        for a in (ad.get("attributes") or []):
            k = a.get("key") or a.get("name")
            v = a.get("value")
            if k:
                attrs[k.lower()] = v

        dorms = _safe_int(attrs.get("bedrooms") or attrs.get("dormitorios"))
        banos = _safe_int(attrs.get("bathrooms") or attrs.get("banos"))
        m2 = _safe_int(attrs.get("surface") or attrs.get("metros_cuadrados"))

        # Fallback regex sobre subject
        if m2 is None:
            m = re.search(r"(\d+)\s*m[²2]", subject, re.IGNORECASE)
            m2 = int(m.group(1)) if m else None
        if dorms is None:
            m = re.search(r"(\d+)\s*(dorm|D\b|amb)", subject, re.IGNORECASE)
            dorms = int(m.group(1)) if m else None
        if banos is None:
            m = re.search(r"(\d+)\s*(ba[ñn]o|B\b)", subject, re.IGNORECASE)
            banos = int(m.group(1)) if m else None

        precio_m2 = int(precio / m2) if m2 and m2 > 0 else None

        # Comuna desde el ad
        loc = ad.get("location") or {}
        comuna_ad = loc.get("name") or comuna.replace("-", " ").title()

        # URL normalizada
        cleaned = re.sub(r"[^a-zA-Z0-9\s]", "", subject.lower())
        cleaned = re.sub(r"\s+", "-", cleaned.strip())
        url = f"https://www.yapo.cl/inmuebles/{cleaned}_{list_id}"

        # Imagen
        img = ad.get("thumbnail") or ad.get("image") or ""
        if img and img.startswith("http://"):
            img = img.replace("http://", "https://")

        return {
            "source_id": f"yapo-{list_id}",
            "source_portal": "yapo",
            "titulo": subject[:200],
            "precio_clp": int(precio),
            "precio_m2": precio_m2,
            "dormitorios": dorms,
            "banos": banos,
            "m2": m2,
            "direccion": (loc.get("name") or "")[:200],
            "comuna": comuna_ad.replace("-", " ").title(),
            "url": url,
            "imagen_url": img or None,
            "activa": True,
            "ultimo_scrape": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.warning(f"Yapo parse error: {e}")
        return None


def _safe_int(v):
    try:
        return int(v) if v is not None else None
    except (ValueError, TypeError):
        return None


def _upsert_property(client, prop: dict) -> str:
    """Inserta o actualiza. Devuelve 'nueva', 'actualizada' o 'error'."""
    try:
        existing = (
            client.table("properties")
            .select("id")
            .eq("source_id", prop["source_id"])
            .limit(1)
            .execute()
        )
        if existing.data:
            client.table("properties").update({
                "precio_clp": prop["precio_clp"],
                "precio_m2": prop.get("precio_m2"),
                "ultimo_scrape": prop["ultimo_scrape"],
                "activa": True,
            }).eq("source_id", prop["source_id"]).execute()
            return "actualizada"
        else:
            client.table("properties").insert(prop).execute()
            return "nueva"
    except Exception as e:
        logger.warning(f"Upsert error: {e}")
        return "error"
