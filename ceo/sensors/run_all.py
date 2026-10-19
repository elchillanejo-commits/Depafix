"""run_all.py — Ejecuta todos los sensores y escribe a ceo_health."""
from __future__ import annotations

import logging
import os

from dotenv import load_dotenv
from supabase import create_client

from ceo.sensors.supabase_probe import probe_supabase
from ceo.sensors.feeds_probe import probe_feeds
from ceo.sensors.railway_probe import probe_railway

load_dotenv()
log = logging.getLogger(__name__)


def run_all() -> dict:
    client = create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SERVICE_ROLE_KEY"],
    )
    return {
        "supabase": probe_supabase(client),
        "feeds": probe_feeds(client),
        "railway": probe_railway(client),
    }


if __name__ == "__main__":
    import json
    logging.basicConfig(level=logging.INFO)
    print(json.dumps(run_all(), indent=2, ensure_ascii=False))
