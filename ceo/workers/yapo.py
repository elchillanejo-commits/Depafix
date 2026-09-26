"""yapo.py — Scraper de arriendos Yapo.cl con Playwright."""
import asyncio
import logging
import os
import re
from datetime import datetime, timezone

from dotenv import load_dotenv
from playwright.async_api import async_playwright
from supabase import create_client

load_dotenv()
logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

BASE_URL = "https://www.yapo.cl"
TIMEOUT_MS = 30000


async def scrape_yapo_worker(params: dict) -> dict:
    """Scrapea arriendos de Yapo por comuna."""
    comunas = params.get("comunas", ["las-condes", "providencia"])
    limite = params.get("limite_por_comuna", 20)

    client = create_client(
        os.getenv("SUPABASE_URL"),
        os.getenv("SUPABASE_SERVICE_ROLE_KEY"),
    )

    total_nuevas = 0
    total_actualizadas = 0
    por_comuna = {}
    errores = []

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        context = await browser.new_context(
            user_agent=USER_AGENT,
            viewport={"width": 1920, "height": 1080},
            locale="es-CL",
        )
        page = await context.new_page()

        for comuna in comunas:
            try:
                nuevos, actualizados = await _scrape_comuna(page, client, comuna, limite)
                total_nuevas += nuevos
                total_actualizadas += actualizados
                por_comuna[comuna] = {"nuevas": nuevos, "actualizadas": actualizados}
                await asyncio.sleep(2)
            except Exception as e:
                logger.error(f"Error en {comuna}: {e}")
                errores.append({"comuna": comuna, "error": str(e)[:100]})

        await browser.close()

    return {
        "ok": True,
        "total_nuevas": total_nuevas,
        "total_actualizadas": total_actualizadas,
        "por_comuna": por_comuna,
        "errores": errores,
        "ejecutado": datetime.now(timezone.utc).isoformat(),
    }


async def _scrape_comuna(page, client, comuna: str, limite: int):
    """Scrapea una comuna de Yapo."""
    nuevas = 0
    actualizadas = 0
    procesados = 0

    # Yapo URL típica: /region-metropolitana/arrendar/departamento?comuna=las-condes
    url = f"{BASE_URL}/region-metropolitana/arrendar/departamento?comuna={comuna}"

    try:
        await page.goto(url, timeout=TIMEOUT_MS, wait_until="domcontentloaded")
        await asyncio.sleep(3)
    except Exception as e:
        logger.warning(f"Yapo goto error: {e}")
        return 0, 0

    cards = await page.query_selector_all("div.ad-card, article.ad-card, div[class*='listing']")
    logger.info(f"Yapo {comuna}: {len(cards)} cards")

    for card in cards[:limite]:
        prop = await _parse_card(card, comuna)
        if not prop:
            continue
        accion = _upsert_property(client, prop)
        if accion == "nueva":
            nuevas += 1
        elif accion == "actualizada":
            actualizadas += 1
        procesados += 1

    return nuevas, actualizadas


async def _parse_card(card, comuna: str):
    """Extrae datos del card de Yapo."""
    try:
        title_el = await card.query_selector("a.title, h3, h2, .title")
        if not title_el:
            return None
        title = (await title_el.inner_text()).strip()

        price_el = await card.query_selector(".price, span[class*='price']")
        if not price_el:
            return None
        precio_txt = (await price_el.inner_text()).strip()
        precio_num = "".join(c for c in precio_txt if c.isdigit())
        if not precio_num or int(precio_num) < 100000:
            return None
        precio = int(precio_num)

        url_el = await card.query_selector("a[href*='/arriendo/']")
        url_item = await url_el.get_attribute("href") if url_el else ""
        if url_item and url_item.startswith("/"):
            url_item = BASE_URL + url_item

        img_el = await card.query_selector("img")
        img_url = await img_el.get_attribute("src") if img_el else None

        source_id = f"yapo-{hash(url_item or title) & 0xFFFFFFFF}"

        m2_match = re.search(r"(\d+)\s*m[²2]", title, re.IGNORECASE)
        dorms_match = re.search(r"(\d+)\s*(dorm|D\b|amb)", title, re.IGNORECASE)
        banos_match = re.search(r"(\d+)\s*(ba[ñn]o|B\b)", title, re.IGNORECASE)

        m2 = int(m2_match.group(1)) if m2_match else None
        dorms = int(dorms_match.group(1)) if dorms_match else None
        banos = int(banos_match.group(1)) if banos_match else None
        precio_m2 = int(precio / m2) if m2 and m2 > 0 else None

        return {
            "source_id": source_id,
            "source_portal": "yapo",
            "titulo": title[:200],
            "precio_clp": precio,
            "precio_m2": precio_m2,
            "dormitorios": dorms,
            "banos": banos,
            "m2": m2,
            "direccion": "",
            "comuna": comuna.replace("-", " ").title(),
            "url": url_item,
            "imagen_url": img_url,
            "activa": True,
            "ultimo_scrape": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.warning(f"Yapo parse error: {e}")
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
        logger.warning(f"Yapo upsert error: {e}")
        return "error"
