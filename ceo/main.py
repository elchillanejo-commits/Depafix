"""ceo/main.py — API FastAPI para el CEO Service."""
import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

# Config
load_dotenv(Path.home() / "PROYECTOS/Proyectos/DepaFix/.env")
import os
from supabase import create_client, Client

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ceo.api")

# Importar scheduler
from ceo.scheduler import start_scheduler


# Modelos
class TaskCreate(BaseModel):
    tipo: str
    parametros: dict = Field(default_factory=dict)
    schedule: Optional[str] = None  # cron expr o None


# Lifespan: arranca scheduler en startup
_scheduler_task: Optional[asyncio.Task] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _scheduler_task
    logger.info("Arrancando scheduler en background...")
    _scheduler_task = asyncio.create_task(start_scheduler())
    yield
    if _scheduler_task:
        _scheduler_task.cancel()
    logger.info("Scheduler detenido")


app = FastAPI(title="DepaFix CEO Service", version="1.0.0", lifespan=lifespan)


# Endpoints

@app.get("/properties-public")
async def properties_public(comuna: str = None, precio_max: int = None):
    """Página pública de propiedades."""
    from fastapi.responses import HTMLResponse
    from ceo.workers.properties import properties_page_worker
    
    params = {}
    if comuna: params["comuna"] = comuna
    if precio_max: params["precio_max"] = precio_max
    
    result = await properties_page_worker(params)
    return HTMLResponse(content=result.get("html", "<h1>Error</h1>"))

@app.get("/health")
def health():
    return {"status": "ok", "ts": datetime.now(timezone.utc).isoformat()}


@app.post("/task")
def create_task(payload: TaskCreate):
    data = {
        "tipo": payload.tipo,
        "parametros": payload.parametros,
        "schedule": payload.schedule,
        "estado": "pending",
    }
    # Si es on-demand: ejecutar inmediatamente (proxima_ejecucion = ahora)
    # Si es scheduled: calcular próxima con croniter
    if payload.schedule:
        try:
            from croniter import croniter
            next_run = croniter(
                payload.schedule, datetime.now(timezone.utc)
            ).get_next(datetime)
            data["proxima_ejecucion"] = next_run.isoformat()
        except Exception as e:
            raise HTTPException(400, f"cron inválido: {e}")
    else:
        data["proxima_ejecucion"] = datetime.now(timezone.utc).isoformat()

    resp = supabase.table("ceo_tasks").insert(data).execute()
    if not resp.data:
        raise HTTPException(500, "No se pudo crear la tarea")
    return {"task": resp.data[0]}


@app.get("/task")
def list_tasks(
    estado: Optional[str] = Query(None),
    tipo: Optional[str] = Query(None),
    limit: int = Query(50, le=500),
):
    q = supabase.table("ceo_tasks").select("*").order("creado_en", desc=True).limit(limit)
    if estado:
        q = q.eq("estado", estado)
    if tipo:
        q = q.eq("tipo", tipo)
    resp = q.execute()
    return {"tasks": resp.data or [], "count": len(resp.data or [])}


@app.get("/task/{task_id}")
def get_task(task_id: int):
    resp = supabase.table("ceo_tasks").select("*").eq("id", task_id).limit(1).execute()
    if not resp.data:
        raise HTTPException(404, "Tarea no encontrada")
    return {"task": resp.data[0]}


@app.delete("/task/{task_id}")
def cancel_task(task_id: int):
    resp = supabase.table("ceo_tasks").update(
        {"estado": "cancelled", "ejecutado_en": datetime.now(timezone.utc).isoformat()}
    ).eq("id", task_id).execute()
    if not resp.data:
        raise HTTPException(404, "Tarea no encontrada")
    return {"cancelled": resp.data[0]}


@app.post("/task/{task_id}/run")
def force_run(task_id: int):
    """Fuerza ejecución inmediata."""
    resp = supabase.table("ceo_tasks").update(
        {"proxima_ejecucion": datetime.now(timezone.utc).isoformat(), "estado": "pending"}
    ).eq("id", task_id).execute()
    if not resp.data:
        raise HTTPException(404, "Tarea no encontrada")
    return {"scheduled_now": resp.data[0]}
