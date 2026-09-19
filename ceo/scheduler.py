"""ceo/scheduler.py — Loop background que ejecuta tareas vencidas."""
import asyncio
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from croniter import croniter
from dotenv import load_dotenv
from supabase import create_client, Client

from ceo.workers import WORKERS

# Config
load_dotenv(Path.home() / "PROYECTOS/Proyectos/DepaFix/.env")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] scheduler: %(message)s",
)
logger = logging.getLogger(__name__)

# Cliente Supabase
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Intervalo entre revisiones
POLL_INTERVAL_SECONDS = 60


async def _execute_task(task: dict) -> None:
    """Ejecuta una tarea y actualiza estado en Supabase."""
    task_id = task["id"]
    tipo = task["tipo"]
    parametros = task.get("parametros") or {}

    logger.info(f"Ejecutando tarea {task_id} ({tipo})")

    # Marcar como running
    supabase.table("ceo_tasks").update(
        {"estado": "running"}
    ).eq("id", task_id).execute()

    t0 = datetime.now(timezone.utc)

    try:
        worker = WORKERS.get(tipo)
        if worker is None:
            raise ValueError(f"Worker '{tipo}' no existe")

        # Ejecutar (async o sync)
        if asyncio.iscoroutinefunction(worker):
            result = await worker(parametros)
        else:
            result = worker(parametros)

        # Guardar resultado
        supabase.table("ceo_results").insert({
            "task_id": task_id,
            "datos": result,
        }).execute()

        duration_ms = int((datetime.now(timezone.utc) - t0).total_seconds() * 1000)

        # Actualizar tarea
        update_data = {
            "estado": "done",
            "resultado": result,
            "ejecutado_en": datetime.now(timezone.utc).isoformat(),
            "duracion_ms": duration_ms,
            "error": None,
        }

        # Si tiene schedule: reprogramar
        schedule = task.get("schedule")
        if schedule:
            try:
                next_run = croniter(
                    schedule,
                    datetime.now(timezone.utc)
                ).get_next(datetime)
                update_data["proxima_ejecucion"] = next_run.isoformat()
                update_data["estado"] = "pending"
                logger.info(f"Tarea {task_id} reprogramada para {next_run}")
            except Exception as e:
                logger.error(f"Error croniter en {task_id}: {e}")
                update_data["error"] = f"croniter: {e}"

        supabase.table("ceo_tasks").update(update_data).eq("id", task_id).execute()
        logger.info(f"Tarea {task_id} completada en {duration_ms}ms")

    except Exception as e:
        logger.error(f"Tarea {task_id} falló: {e}")
        supabase.table("ceo_tasks").update({
            "estado": "failed",
            "error": str(e)[:500],
            "ejecutado_en": datetime.now(timezone.utc).isoformat(),
        }).eq("id", task_id).execute()


async def _tick() -> None:
    """Un ciclo: busca tareas vencidas y las ejecuta."""
    try:
        now = datetime.now(timezone.utc).isoformat()
        resp = (
            supabase.table("ceo_tasks")
            .select("*")
            .lte("proxima_ejecucion", now)
            .eq("estado", "pending")
            .limit(10)
            .execute()
        )

        tasks = resp.data or []
        if not tasks:
            return

        logger.info(f"Encontradas {len(tasks)} tareas vencidas")
        for task in tasks:
            await _execute_task(task)

    except Exception as e:
        logger.error(f"Error en tick: {e}")


async def start_scheduler() -> None:
    """Loop principal del scheduler. Corre infinito."""
    logger.info("Scheduler iniciado — polling cada 60s")
    logger.info(f"WORKERS disponibles: {list(WORKERS.keys())}")
    while True:
        try:
            await _tick()
        except Exception as e:
            logger.error(f"Error no capturado en scheduler: {e}")

        await asyncio.sleep(POLL_INTERVAL_SECONDS)
