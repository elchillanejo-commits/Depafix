"""Registry de workers del CEO Service con import lazy."""
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


# Workers esenciales (post-auditoría DT)
_safe_import("properties_page", "ceo.workers.properties", "properties_page_worker")
_safe_import("cleanup_old_tasks", "ceo.workers.cleanup", "cleanup_old_tasks_worker")
_safe_import("notifier_telegram", "ceo.workers.notifier", "notifier_telegram_worker")
_safe_import("scrape_sodimac", "ceo.workers.sodimac", "scrape_sodimac_worker")
_safe_import("scrape_toctoc", "ceo.workers.toctoc", "scrape_toctoc_worker")
_safe_import("supervisor_trading", "ceo.workers.supervisor", "supervisor_trading_worker")

logger.info(f"Workers cargados: {len(WORKERS)}")
if _LOAD_ERRORS:
    logger.warning(f"Workers con error: {list(_LOAD_ERRORS.keys())}")
_safe_import("calculate_market_stats", "ceo.workers.market_stats", "calculate_market_stats_worker")
_safe_import("kraken_feed", "ceo.workers.kraken_feed", "kraken_feed_worker")
_safe_import("health_probe", "ceo.workers.health_probe", "health_probe_worker")
_safe_import("rules_evaluator", "ceo.workers.rules_evaluator", "rules_evaluator_worker")
_safe_import("reporter_daily", "ceo.workers.reporter_daily", "reporter_daily_worker")
_safe_import("demo_probes", "ceo.workers.demo_probes", "demo_probes_worker")
_safe_import("properties_probe", "ceo.workers.properties_probe", "properties_probe_worker")
_safe_import("properties_duplicados", "ceo.workers.properties_duplicados", "properties_duplicados_worker")
_safe_import("inventory_probe", "ceo.workers.inventory_probe", "inventory_probe_worker")
_safe_import("caja_probe", "ceo.workers.caja_probe", "caja_probe_worker")
_safe_import("flota_probe", "ceo.workers.flota_probe", "flota_probe_worker")
