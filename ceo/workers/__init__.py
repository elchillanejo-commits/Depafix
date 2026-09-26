"""Registry de workers del CEO Service con import lazy.

Cada worker se importa dentro de try/except para que falte una
dependencia externa (ej: playwright) no rompa todo el registry.
"""
import logging

logger = logging.getLogger(__name__)

WORKERS = {}
_LOAD_ERRORS = {}


def _safe_import(nombre, modulo, funcion):
    """Intenta importar un worker. Si falla, lo registra en _LOAD_ERRORS."""
    try:
        mod = __import__(modulo, fromlist=[funcion])
        WORKERS[nombre] = getattr(mod, funcion)
    except Exception as e:
        _LOAD_ERRORS[nombre] = f"{type(e).__name__}: {e}"
        logger.warning(f"Worker '{nombre}' no cargado: {e}")


# Cargar todos los workers (import lazy)
_safe_import("noop", "ceo.workers.noop", "noop_worker")
_safe_import("monitor_bot", "ceo.workers.bot_health", "monitor_bot_worker")
_safe_import("scrape_sodimac", "ceo.workers.sodimac", "scrape_sodimac_worker")
_safe_import("digest_diario", "ceo.workers.digest", "digest_diario_worker")
_safe_import("youtube_ingest", "ceo.workers.youtube", "youtube_ingest_worker")
_safe_import("youtube_batch", "ceo.workers.youtube_batch", "youtube_batch_worker")
_safe_import("query_knowledge", "ceo.workers.query", "query_knowledge_worker")
_safe_import("resumen_ia", "ceo.workers.resumen", "resumen_ia_worker")
_safe_import("notifier_telegram", "ceo.workers.notifier", "notifier_telegram_worker")
_safe_import("cleanup_old_tasks", "ceo.workers.cleanup", "cleanup_old_tasks_worker")
_safe_import("analizar_tendencias", "ceo.workers.tendencias", "analizar_tendencias_worker")
_safe_import("properties_page", "ceo.workers.properties", "properties_page_worker")
_safe_import("scrape_mercadolibre", "ceo.workers.mercadolibre", "scrape_mercadolibre_worker")
_safe_import("scrape_yapo", "ceo.workers.yapo", "scrape_yapo_worker")

# Reportar estado
logger.info(f"Workers cargados: {len(WORKERS)}")
if _LOAD_ERRORS:
    logger.warning(f"Workers con error: {list(_LOAD_ERRORS.keys())}")
