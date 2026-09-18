from ceo.workers.noop import noop_worker
from ceo.workers.bot_health import monitor_bot_worker
from ceo.workers.sodimac import scrape_sodimac_worker

WORKERS = {
    "noop": noop_worker,
    "monitor_bot": monitor_bot_worker,
    "scrape_sodimac": scrape_sodimac_worker,
}
