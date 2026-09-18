"""bot_health.py — Monitorea la salud del bot de trading vía Supabase."""
import os
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from supabase import create_client

load_dotenv(os.path.expanduser("~/PROYECTOS/Proyectos/DepaFix/.env"))


async def monitor_bot_worker(params: dict) -> dict:
    """
    Verifica que el bot de trading esté activo.

    Params:
        horas: ventana a analizar (default 1)

    Returns:
        dict con métricas y estado de salud
    """
    horas = params.get("horas", 1)
    corte = (datetime.now(timezone.utc) - timedelta(hours=horas)).isoformat()

    client = create_client(
        os.getenv("SUPABASE_URL"),
        os.getenv("SUPABASE_SERVICE_ROLE_KEY"),
    )

    # Traer señales recientes
    resp = (
        client.table("operaciones_ejecutadas")
        .select("senal,activo,timestamp")
        .gte("timestamp", corte)
        .execute()
    )
    señales = resp.data or []

    # Contar por tipo
    compras = sum(1 for s in señales if s["senal"] == "COMPRA")
    ventas = sum(1 for s in señales if s["senal"] == "VENTA")
    esperas = sum(1 for s in señales if s["senal"] == "ESPERA")

    # Detección de anomalías
    saludable = len(señales) >= 4  # al menos 1 ciclo por par en la ventana

    return {
        "ventana_horas": horas,
        "total_señales": len(señales),
        "compras": compras,
        "ventas": ventas,
        "esperas": esperas,
        "saludable": saludable,
        "verificado_en": datetime.now(timezone.utc).isoformat(),
    }
