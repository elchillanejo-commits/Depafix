"""sodimac.py — Scraper de precios de Sodimac.cl (estructura lista)."""
import asyncio
from datetime import datetime, timezone

try:
    import requests
    REQUESTS_OK = True
except ImportError:
    REQUESTS_OK = False


async def scrape_sodimac_worker(params: dict) -> dict:
    """
    Scraper de Sodimac — estructura lista, integración real pendiente.

    Params:
        queries: lista de productos (ej: ["cemento", "fierro 8mm"])
        region: código de región (default "RM")

    Returns:
        dict con productos encontrados por query

    NOTA: La integración real con Playwright/Scrapy se hará en la próxima
    sesión. Por ahora devuelve estructura válida para probar el pipeline.
    """
    queries = params.get("queries", ["cemento"])
    region = params.get("region", "RM")

    if not REQUESTS_OK:
        raise RuntimeError("requests no está instalado")

    resultados = {}
    for q in queries:
        # TODO: integración real — Playwright + selectores CSS de Sodimac
        # Por ahora: simulación determinista basada en query
        await asyncio.sleep(0.5)
        resultados[q] = [
            {
                "nombre": f"{q.title()} (simulado)",
                "precio": 9990 + len(q) * 100,
                "sku": f"SKU-{q.upper()[:4]}-001",
                "url": f"https://www.sodimac.cl/sodimac-cl/search?Ntt={q}",
                "stock": True,
                "region": region,
            }
        ]

    return {
        "queries_ejecutadas": queries,
        "region": region,
        "total_productos": sum(len(v) for v in resultados.values()),
        "resultados": resultados,
        "nota": "Simulación — integración real pendiente",
        "ejecutado": datetime.now(timezone.utc).isoformat(),
    }
