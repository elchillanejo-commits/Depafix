from ceo.workers.noop import noop_worker
from ceo.workers.bot_health import monitor_bot_worker
from ceo.workers.sodimac import scrape_sodimac_worker
from ceo.workers.digest import digest_diario_worker
from ceo.workers.youtube import youtube_ingest_worker
from ceo.workers.youtube_batch import youtube_batch_worker
from ceo.workers.query import query_knowledge_worker
from ceo.workers.resumen import resumen_ia_worker
from ceo.workers.notifier import notifier_telegram_worker

WORKERS = {
    "noop": noop_worker,
    "monitor_bot": monitor_bot_worker,
    "scrape_sodimac": scrape_sodimac_worker,
    "digest_diario": digest_diario_worker,
    "youtube_ingest": youtube_ingest_worker,
    "youtube_batch": youtube_batch_worker,
    "query_knowledge": query_knowledge_worker,
    "resumen_ia": resumen_ia_worker,
    "notifier_telegram": notifier_telegram_worker,
}
