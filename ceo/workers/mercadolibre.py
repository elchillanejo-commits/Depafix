"""mercadolibre.py — Scraper de arriendos MLC con Playwright."""
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

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
BASE_URL = "https://listado.mercadolibre.cl"
TIMEOUT_MS = 60000

async def scrape_mercadolibre_worker(params: dict) -> dict:
    comunas = params.get("comunas", ["las-condes"])
    limite = params.get("limite_por_comuna", 5)
    client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_ROLE_KEY"))
    total_nuevas = 0
    por_comuna = {}

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True, args=["--no-sandbox", "--disable-blink-features=AutomationControlled"])
        context = await browser.new_context(user_agent=USER_AGENT)
        page = await context.new_page()

        for comuna in comunas:
            comuna_url = f"{BASE_URL}/departamento-arriendo/{comuna}/_NoIndex_True"
            try:
                await page.goto(comuna_url, timeout=TIMEOUT_MS, wait_until="networkidle")
                await asyncio.sleep(5)
                # Selectores basados en la estructura real de ML
                cards = await page.query_selector_all(".ui-search-result__wrapper")
                for card in cards[:limite]:
                    prop = await _parse_card(card, comuna)
                    if prop:
                        client.table("properties").upsert(prop).execute()
                        total_nuevas += 1
            except Exception as e:
                logger.error(f"Error {comuna}: {e}")
        await browser.close()
    return {"ok": True, "total": total_nuevas}

async def _parse_card(card, comuna: str):
    try:
        title_el = await card.query_selector(".ui-search-item__title")
        price_el = await card.query_selector(".andes-money-amount__fraction")
        url_el = await card.query_selector("a.ui-search-item__group__element")
        
        title = await title_el.inner_text()
        precio = int("".join(filter(str.isdigit, await price_el.inner_text())))
        url = await url_el.get_attribute("href")
        
        return {
            "source_id": f"mlc-{re.search(r'MLC-(\d+)', url).group(1)}",
            "titulo": title,
            "precio_clp": precio,
            "url": url,
            "comuna": comuna,
            "ultimo_scrape": datetime.now(timezone.utc).isoformat()
        }
    except: return None
