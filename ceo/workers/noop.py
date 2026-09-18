"""Worker de prueba."""
from datetime import datetime


async def noop_worker(params: dict) -> dict:
    return {
        "message": "noop ejecutado",
        "input": params,
        "ts": datetime.now().isoformat()
    }
