"""supervisor.py — Audita el bot de Kraken y activa kill-switch."""
import logging
import os
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from supabase import create_client

load_dotenv()
logger = logging.getLogger(__name__)


async def supervisor_trading_worker(params: dict) -> dict:
    """Audita el bot y pausa si rompe reglas de riesgo."""
    horas = params.get("horas", 24)
    auto_pausar = params.get("auto_pausar", True)

    client = create_client(
        os.environ.get("SUPABASE_URL"),
        os.environ.get("SUPABASE_SERVICE_ROLE_KEY"),
    )

    corte = (datetime.now(timezone.utc) - timedelta(hours=horas)).isoformat()
    resp = (
        client.table("operaciones_ejecutadas")
        .select("senal,activo,precio_entrada,timestamp")
        .gte("timestamp", corte)
        .order("timestamp", desc=True)
        .execute()
    )
    ops = resp.data or []

    # Métricas
    total = len(ops)
    direccionales = [o for o in ops if o["senal"] in ("COMPRA", "VENTA")]

    # Pérdidas consecutivas (simplificado: cuenta ESPERA tras COMPRA/VENTA)
    perdidas_cons = 0
    for o in ops:
        if o["senal"] in ("COMPRA", "VENTA"):
            perdidas_cons += 1
        elif o["senal"] == "ESPERA":
            break

    # Win rate (aproximado: COMPRA sobre total direccional)
    if direccionales:
        compras = sum(1 for o in direccionales if o["senal"] == "COMPRA")
        win_rate = compras / len(direccionales)
    else:
        win_rate = 0.0

    # Operaciones por hora
    ops_por_hora = total / max(horas, 1)

    # Evaluar reglas
    razon = "Sin violaciones"
    veredicto = "OK"
    pausar = False

    if perdidas_cons >= 3:
        veredicto = "PAUSAR"
        razon = f"{perdidas_cons} pérdidas consecutivas detectadas"
        pausar = True
    elif win_rate < 0.30 and len(direccionales) >= 10:
        veredicto = "PAUSAR"
        razon = f"Win rate bajo: {win_rate:.1%}"
        pausar = True
    elif ops_por_hora > 100:
        veredicto = "PAUSAR"
        razon = f"Posible loop: {ops_por_hora:.1f} ops/hora"
        pausar = True

    # Activar kill-switch
    if pausar and auto_pausar:
        try:
            client.table("bot_control").insert({
                "pausado": True,
                "motivo": razon,
                "activado_en": datetime.now(timezone.utc).isoformat(),
                "datos_contexto": {
                    "perdidas_consecutivas": perdidas_cons,
                    "win_rate": win_rate,
                    "ops_por_hora": ops_por_hora,
                },
            }).execute()
            logger.warning(f"🛑 Bot pausado: {razon}")
        except Exception as e:
            logger.error(f"Error guardando pausa: {e}")

    return {
        "ok": True,
        "veredicto": veredicto,
        "razon": razon,
        "metricas": {
            "total_operaciones": total,
            "perdidas_consecutivas": perdidas_cons,
            "win_rate": round(win_rate, 3),
            "ops_por_hora": round(ops_por_hora, 2),
        },
        "pausado": pausar,
        "ejecutado": datetime.now(timezone.utc).isoformat(),
    }
