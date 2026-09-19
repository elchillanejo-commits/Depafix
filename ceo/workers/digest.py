"""digest.py — Digest diario del sistema DepaFix (100% Supabase)."""
import logging
from datetime import datetime, timedelta, timezone

import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv(os.path.expanduser("~/PROYECTOS/Proyectos/DepaFix/.env"))
logger = logging.getLogger(__name__)


async def digest_diario_worker(params: dict) -> dict:
    """
    Genera digest del sistema: señales + health + proyectos.
    100% basado en datos de Supabase (no scraping).
    """
    client = create_client(
        os.getenv("SUPABASE_URL"),
        os.getenv("SUPABASE_SERVICE_ROLE_KEY"),
    )

    ahora = datetime.now(timezone.utc)
    corte_24h = (ahora - timedelta(hours=24)).isoformat()

    # 1. Señales últimas 24h
    ops = (
        client.table("operaciones_ejecutadas")
        .select("senal,activo,timestamp")
        .gte("timestamp", corte_24h)
        .execute()
    ).data or []

    # 2. Contar por señal
    por_senal = {"COMPRA": 0, "VENTA": 0, "ESPERA": 0}
    por_activo = {}
    for op in ops:
        s = op.get("senal", "?")
        a = op.get("activo", "?")
        por_senal[s] = por_senal.get(s, 0) + 1
        por_activo[a] = por_activo.get(a, 0) + 1

    # 3. Tasks del CEO últimas 24h
    tasks = (
        client.table("ceo_tasks")
        .select("estado,tipo")
        .gte("creado_en", corte_24h)
        .execute()
    ).data or []

    tasks_por_estado = {"pending": 0, "done": 0, "failed": 0, "running": 0}
    for t in tasks:
        e = t.get("estado", "?")
        tasks_por_estado[e] = tasks_por_estado.get(e, 0) + 1

    # 4. Última vela registrada (actividad del bot)
    vela = (
        client.table("velas_cripto")
        .select("par,tiempo")
        .order("tiempo", desc=True)
        .limit(1)
        .execute()
    ).data or []

    ultima_vela = vela[0] if vela else {}

    return {
        "ventana_horas": 24,
        "ejecutado": ahora.isoformat(),
        "señales": {
            "total": len(ops),
            "por_tipo": por_senal,
            "por_activo": por_activo,
        },
        "ceo_tasks": {
            "total": len(tasks),
            "por_estado": tasks_por_estado,
        },
        "ultima_vela": ultima_vela,
        "salud": "ok" if len(ops) > 10 else "degradada",
    }
