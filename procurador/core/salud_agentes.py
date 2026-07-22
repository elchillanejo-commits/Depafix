"""
salud_agentes.py -- helper compartido para reportar el estado de un proceso
('HEALTHY'/'CRITICAL') a la tabla salud_agentes (ver
01_SERVIU/create_salud_agentes.sql), con reintentos exponenciales (backoff, ver
core/resiliencia.py). Usado por core/trade_agent.py y
src/trading/trading_orchestrator.py para que Siegfried (u otro monitor)
sepa si un proceso corrió bien sin tener que entrar al servidor ni parsear
logs.
"""
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from core.resiliencia import red_segura, RedFailSafeError

logger = logging.getLogger(__name__)

TABLA_SALUD = "salud_agentes"

# La tabla vive con un CHECK constraint que acepta
# ('online','offline','error','warning') -- confirmado contra
# information_schema.columns y pg_constraint en vivo, 2026-07-21 (ver
# sql/create_salud_agentes.sql, ya actualizado). Este código solo escribe
# 'online'/'error' porque el resto del repo (trading_orchestrator.py, etc.)
# sigue usando HEALTHY/CRITICAL como vocabulario semantico -- se traduce
# aca, en el unico punto de escritura, en vez de tocar todos los call sites.
_ESTADO_A_COLUMNA = {"HEALTHY": "online", "CRITICAL": "error"}


@red_segura()
def _insertar_salud(cliente, fila: Dict[str, Any]) -> None:
    cliente.table(TABLA_SALUD).insert(fila).execute()


def reportar_salud(cliente, proceso: str, estado: str, detalle: str = "",
                    metricas: Optional[Dict[str, Any]] = None) -> None:
    """Escribe una fila en salud_agentes. `cliente` debe ser el cliente
    service_role de Supabase (DatabaseManager.get_service_client()) -- RLS
    bloquea a la key anon a propósito, ver 01_SERVIU/create_salud_agentes.sql.

    Nunca lanza: reportar salud no debe hacer caer al proceso que está
    siendo monitoreado. Si el cliente no está disponible o Supabase no
    responde tras los reintentos, se loguea y se sigue."""
    fila = {
        # Nombres de columna reales en Supabase (agente/mensaje/ultimo_ciclo,
        # no proceso/detalle/corrido_at -- ver create_salud_agentes.sql vs
        # esquema vivo, divergieron en algun momento).
        "agente": proceso,
        "estado": _ESTADO_A_COLUMNA.get(estado, estado),
        "mensaje": detalle,
        "metricas": metricas or {},
        "ultimo_ciclo": datetime.now(timezone.utc).isoformat(),
    }
    if not cliente:
        logger.error("Cliente Supabase (service_role) no disponible: no se pudo reportar salud (%s) de %s.",
                     estado, proceso)
        return
    try:
        _insertar_salud(cliente, fila)
        logger.info("Salud reportada a %s: %s/%s (%s)", TABLA_SALUD, proceso, estado, detalle)
    except RedFailSafeError as e:
        logger.error("No se pudo reportar salud de %s a %s tras reintentos: %s", proceso, TABLA_SALUD, e)
