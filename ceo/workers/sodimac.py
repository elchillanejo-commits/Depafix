"""sodimac.py — Scraper REAL de Sodimac.cl usando Playwright async."""
import asyncio
import logging
from datetime import datetime, timezone

from playwright.async_api import async_playwright

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

TIMEOUT_MS = 30000


async def scrape_sodimac_worker(params: dict) -> dict:
    """
    Scraper real de Sodimac.cl.
    
    Params:
        queries: lista de productos (ej: ["cemento", "fierro 8mm"])
        region: código región (default "RM")
        limite_por_query: máximo productos por query (default 10)
    
    Returns:
        dict con productos encontrados por query
    """
    queries = params.get("queries", ["cemento"])
    region = params.get("region", "RM")
    limite = params.get("limite_por_query", 10)

    t0 = datetime.now(timezone.utc)
    resultados = {}

    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )
            context = await browser.new_context(
                user_agent=USER_AGENT,
                viewport={"width": 1920, "height": 1080},
                locale="es-CL",
                timezone_id="America/Santiago",
            )
            page = await context.new_page()

            # Bloquear recursos innecesarios para acelerar
            await page.route(
                "**/*.{png,jpg,jpeg,gif,svg,woff,woff2,ttf,mp4,webm}",
                lambda route: route.abort(),
            )

            for q in queries:
                try:
                    productos = await _scrape_query(page, q, limite)
                    resultados[q] = productos
                    logger.info(f"Query '{q}': {len(productos)} productos")
                except Exception as e:
                    logger.error(f"Query '{q}' falló: {e}")
                    resultados[q] = []
                await asyncio.sleep(2)  # rate limiting

            await browser.close()

    except Exception as e:
        logger.error(f"Playwright falló: {e}")
        return {
            "error": str(e)[:200],
            "queries_ejecutadas": queries,
            "ejecutado": datetime.now(timezone.utc).isoformat(),
        }

    duracion_ms = int((datetime.now(timezone.utc) - t0).total_seconds() * 1000)

    return {
        "queries_ejecutadas": queries,
        "region": region,
        "total_productos": sum(len(v) for v in resultados.values()),
        "por_query": resultados,
        "duracion_ms": duracion_ms,
        "ejecutado": datetime.now(timezone.utc).isoformat(),
    }


async def _scrape_query(page, query: str, limite: int) -> list[dict]:
    """Raspa una sola query de búsqueda."""
    url = f"https://www.sodimac.cl/sodimac-cl/search?Ntt={query}"
    logger.info(f"Navegando: {url}")

    await page.goto(url, timeout=TIMEOUT_MS, wait_until="domcontentloaded")
    await asyncio.sleep(3)  # esperar render JS

    # Selectores de Sodimac (ajustar si cambia su HTML)
    cards = await page.query_selector_all(".pod-pod, [data-testid='product-card']")

    productos = []
    for card in cards[:limite]:
        try:
            prod = await _parse_producto(card)
            if prod:
                productos.append(prod)
        except Exception:
            continue

    return productos


async def _parse_producto(card) -> dict | None:
    """Parsea un card de producto."""
    nombre_el = await card.query_selector(".pod-subTitle, [data-testid='product-title']")
    precio_el = await card.query_selector(".prices-0, [data-testid='price']")
    link_el = await card.query_selector("a.pod-link, a[href*='/producto/']")

    if not nombre_el or not precio_el:
        return None

    nombre = (await nombre_el.inner_text()).strip()
    precio_txt = (await precio_el.inner_text()).strip()
    url = await link_el.get_attribute("href") if link_el else None

    # Limpiar precio: "$8.990" → 8990
    precio_num = "".join(c for c in precio_txt if c.isdigit())
    precio = int(precio_num) if precio_num else 0

    if not nombre or precio == 0:
        return None

    return {
        "nombre": nombre,
        "precio": precio,
        "url": url,
        "query_origen": "",
        "scraped_at": datetime.now(timezone.utc).isoformat(),
    }
