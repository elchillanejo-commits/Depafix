"""railway_probe.py — Status de servicios Railway via CLI (fail-open).

Si el CLI no está disponible (CEO corre en Railway, no en Vostro),
retorna status="skip" sin fallar. El sensor funciona desde ambos lados.
"""
from __future__ import annotations

import logging
import shutil
import subprocess
from typing import Any

from ceo.state import registrar_health

log = logging.getLogger(__name__)
TIMEOUT_S = 15


def _cli_disponible() -> bool:
    return shutil.which("railway") is not None


def probe_railway(client: Any, timeout: int = TIMEOUT_S) -> dict:
    """Lee estado de servicios Railway vía `railway status`."""
    if not _cli_disponible():
        registrar_health(
            client, "railway", "services", "skip", None,
            {"razon": "railway CLI no disponible (probable CEO en Railway)"},
        )
        return {"status": "skip", "razon": "cli_no_disponible"}

    try:
        r = subprocess.run(
            ["railway", "status"],
            capture_output=True, text=True, timeout=timeout,
        )
        out = (r.stdout or "") + (r.stderr or "")
    except subprocess.TimeoutExpired:
        registrar_health(client, "railway", "services", "warn",
                         timeout * 1000, {"razon": "timeout"})
        return {"status": "warn", "razon": "timeout"}
    except Exception as e:
        log.warning("probe_railway falló: %s", e)
        registrar_health(client, "railway", "services", "fail",
                         None, {"error": str(e)[:150]})
        return {"status": "fail", "error": str(e)[:150]}

    status = "ok"
    if r.returncode != 0:
        status = "fail"
    elif "Deploying" in out or "Building" in out:
        status = "warn"

    payload = {
        "online": out.count("Online"),
        "offline": out.count("Offline"),
        "returncode": r.returncode,
    }
    registrar_health(client, "railway", "services", status, None, payload)
    return {"status": status, **payload}


if __name__ == "__main__":
    import json
    import os

    from dotenv import load_dotenv
    from supabase import create_client

    load_dotenv()
    logging.basicConfig(level=logging.INFO)
    c = create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SERVICE_ROLE_KEY"],
    )
    print(json.dumps(probe_railway(c), indent=2, ensure_ascii=False))
