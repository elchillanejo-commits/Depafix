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
    await asyncio.sleep(8)  # Tiempo adicional

    # Selectores de Sodimac (ajustar si cambia su HTML)
    # Debug: imprimir estructura para inspeccionar
    # logger.info(f"HTML: {await page.content()}")
    
    # Reemplazar la lógica de debug por una más directa basada en la estructura real
    # He detectado que hay elementos que contienen precios. Vamos a buscar 
    # los elementos que contienen precios y subir un poco en el árbol para obtener el card.
    
    # Selector probado para Sodimac (basado en inspección común)
    cards = await page.query_selector_all("div[class*='jsx-'][class*='product']")
    logger.info(f"Cards encontradas: {len(cards)}")
    
    # Intentar identificar card por su contenido de precio
    productos = []
    # Filtrar tarjetas que contengan un precio (tengan signo $)
    for card in cards:
        text = await card.text_content()
        if "$" in text:
            # Aquí implementaría la lógica de parseo, por ahora solo contar
            productos.append(card)
    logger.info(f"Cards con posible precio: {len(productos)}")
    
    results = []
    for card in productos[:limite]:
        try:
            prod = await _parse_producto(card)
            if prod:
                results.append(prod)
            else:
                # Debug: ver por qué no se parseó
                text = await card.text_content()
                logger.warning(f"No se pudo parsear card: {text[:50]}")
        except Exception as e:
            logger.error(f"Error parseando card: {e}")
            continue
    
    # La lógica actual devuelve duplicados porque el mismo producto 
    # aparece en distintos niveles de cards (card padre, card hijo).
    # Filtremos los resultados para tener productos únicos por nombre.
    
    unique_productos = {}
    for p in results:
        if p["nombre"] not in unique_productos:
            unique_productos[p["nombre"]] = p
            
    return list(unique_productos.values())


async def _parse_producto(card) -> dict | None:
    """Parsea un card de producto."""
    # Intentar buscar elementos con selectores más flexibles
    # Usar texto directo si los selectores fallan
    text = await card.text_content()
    # Buscar el precio en el texto (ej: $12.990)
    import re
    # Regex para encontrar precios chilenos
    precio_match = re.search(r'\$\s*([\d\.]+)', text)
    
    if not precio_match:
        return None
    
    precio_str = precio_match.group(1).replace(".", "").replace(",", "")
    precio = int(precio_str)
    
    # Intentar limpiar más el nombre
    nombre_raw = text.split(precio_match.group(0))[0].strip()
    # Eliminar textos tipo "Comparar" o similares que suelen estar al inicio
    # También limpiar paréntesis basura al final
    nombre = re.sub(r'^(Comparar|Cargar)', '', nombre_raw).strip()
    nombre = re.sub(r'\(\d+\)$', '', nombre).strip()
    
    # Limpieza adicional: eliminar el texto "(9)" que aparece intermedio
    nombre = re.sub(r'\(\d+\)', '', nombre).strip()
    
    # Ignorar elementos que solo son números o texto de marketing
    if len(nombre) < 5:
        return None
    
    if not nombre or precio == 0:
        return None

    return {
        "nombre": nombre,
        "precio": precio,
        "url": "N/A", # Difícil sin selector
        "query_origen": "",
        "scraped_at": datetime.now(timezone.utc).isoformat(),
    }
