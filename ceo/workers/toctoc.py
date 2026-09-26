"""toctoc.py — Scraper TocToc vía __NEXT_DATA__ (sin Playwright)."""
import asyncio
import json
import logging
import os
import re
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()
logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
)

BASE_URL = "https://www.toctoc.com"


async def scrape_toctoc_worker(params: dict) -> dict:
    """Scrapea arriendos de TocToc por comuna."""
    comunas = params.get("comunas", ["las-condes", "providencia"])
    limite = params.get("limite_por_comuna", 30)
    tipo = params.get("tipo", "departamento")

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
                client, comuna, tipo, limite
            )
            total_nuevas += nuevas
            total_actualizadas += actualizadas
            por_comuna[comuna] = {"nuevas": nuevas, "actualizadas": actualizadas}
            await asyncio.sleep(2)
        except Exception as e:
            logger.error(f"Error TocToc {comuna}: {e}")
            errores.append({"comuna": comuna, "error": str(e)[:150]})

    return {
        "ok": True,
        "total_nuevas": total_nuevas,
        "total_actualizadas": total_actualizadas,
        "por_comuna": por_comuna,
        "errores": errores,
        "ejecutado": datetime.now(timezone.utc).isoformat(),
    }


async def _scrape_comuna(client, comuna: str, tipo: str, limite: int):
    """Scrapea una comuna extrayendo __NEXT_DATA__."""
    url = f"{BASE_URL}/arriendo/{tipo}/region-metropolitana/{comuna}"

    try:
        resp = requests.get(
            url,
            headers={"User-Agent": USER_AGENT, "Accept-Language": "es-CL"},
            timeout=20,
        )
        if resp.status_code != 200:
            logger.warning(f"TocToc {comuna} HTTP {resp.status_code}")
            return 0, 0

        soup = BeautifulSoup(resp.text, "html.parser")
        script = soup.find("script", {"id": "__NEXT_DATA__"})
        if not script:
            logger.warning(f"TocToc {comuna}: sin __NEXT_DATA__")
            return 0, 0

        data = json.loads(script.string)
        props = _extract_props(data)

        logger.info(f"TocToc {comuna}: {len(props)} props encontradas")

        nuevas = 0
        actualizadas = 0
        for p in props[:limite]:
            prop = _parse_prop(p, comuna)
            if not prop:
                continue
            accion = _upsert_property(client, prop)
            if accion == "nueva":
                nuevas += 1
            elif accion == "actualizada":
                actualizadas += 1

        return nuevas, actualizadas
    except Exception as e:
        logger.warning(f"TocToc loop error: {e}")
        return 0, 0


def _extract_props(data: dict) -> list:
    """Busca recursivamente listas de propiedades en el JSON."""
    results = []

    def walk(node, depth=0):
        if depth > 8:
            return
        if isinstance(node, dict):
            for k, v in node.items():
                if k in ("results", "properties", "listado", "items", "ads", "propiedades", "cards"):
                    if isinstance(v, list) and v and isinstance(v[0], dict):
                        results.extend(v)
                walk(v, depth + 1)
        elif isinstance(node, list):
            for item in node[:50]:
                walk(item, depth + 1)

    walk(data)

    # Filtrar los que parezcan propiedades (tienen precio o título)
    filtrados = []
    for r in results:
        if isinstance(r, dict) and (
            r.get("precio") or r.get("price") or r.get("titulo") or r.get("title")
        ):
            filtrados.append(r)

    return filtrados


def _parse_prop(p: dict, comuna: str):
    """Parsea una propiedad de TocToc."""
    try:
        # ID
        pid = p.get("id") or p.get("codigo") or p.get("propertyId")
        if not pid:
            return None

        # Título
        titulo = (p.get("titulo") or p.get("title") or p.get("nombre") or "").strip()
        if not titulo:
            return None

        # Precio
        precio = p.get("precio") or p.get("price") or p.get("precio_peso") or 0
        if isinstance(precio, dict):
            precio = precio.get("amount") or precio.get("valor") or 0
        precio = int(precio) if precio else 0
        if precio <= 0:
            return None

        # Dorms, baños, m2
        dorms = p.get("dormitorios") or p.get("bedrooms") or p.get("dorms")
        banos = p.get("baños") or p.get("banos") or p.get("bathrooms")
        m2 = p.get("m2_superficie") or p.get("m2_construido") or p.get("m2") or p.get("superficie")

        dorms = _safe_int(dorms)
        banos = _safe_int(banos)
        m2 = _safe_int(m2)

        if m2 is None:
            m = re.search(r"(\d+)\s*m[²2]", titulo, re.IGNORECASE)
            m2 = int(m.group(1)) if m else None

        precio_m2 = int(precio / m2) if m2 and m2 > 0 else None

        # URL
        url_item = p.get("url") or p.get("link") or f"{BASE_URL}/propiedades/{pid}"
        if url_item and url_item.startswith("/"):
            url_item = BASE_URL + url_item

        # Imagen
        img = p.get("imagen") or p.get("image") or p.get("foto") or ""
        if isinstance(img, list) and img:
            img = img[0]
        if isinstance(img, dict):
            img = img.get("url") or img.get("src") or ""

        return {
            "source_id": f"toctoc-{pid}",
            "source_portal": "toctoc",
            "titulo": titulo[:200],
            "precio_clp": precio,
            "precio_m2": precio_m2,
            "dormitorios": dorms,
            "banos": banos,
            "m2": m2,
            "direccion": (p.get("direccion") or p.get("address") or "")[:200],
            "comuna": (p.get("comuna") or comuna.replace("-", " ").title()),
            "url": url_item,
            "imagen_url": img or None,
            "activa": True,
            "ultimo_scrape": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.warning(f"TocToc parse error: {e}")
        return None


def _safe_int(v):
    if v is None:
        return None
    try:
        return int(str(v).split(".")[0])
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
