import os
from datetime import datetime, timedelta, timezone
from supabase import create_client

async def cleanup_old_tasks_worker(params: dict) -> dict:
    dias_max = params.get("dias_max", 30)
    estados = params.get("estados", ["done", "failed"])
    dry_run = params.get("dry_run", False)
    
    client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_ROLE_KEY"))
    
    limite_fecha = (datetime.now(timezone.utc) - timedelta(days=dias_max)).isoformat()
    
    # 1. Identificar tareas a limpiar
    query = client.table("ceo_tasks").select("id").lt("creado_en", limite_fecha).in_("estado", estados)
    tasks = query.execute().data
    
    candidatas = len(tasks)
    if candidatas == 0:
        return {"ok": True, "candidatas": 0, "eliminadas": 0, "dry_run": dry_run, "ejecutado": datetime.now(timezone.utc).isoformat()}
        
    task_ids = [t["id"] for t in tasks]
    
    if dry_run:
        return {"ok": True, "candidatas": candidatas, "eliminadas": 0, "dry_run": dry_run, "ejecutado": datetime.now(timezone.utc).isoformat()}
        
    # 2. Eliminar resultados asociados (evitar error FK)
    client.table("ceo_results").delete().in_("task_id", task_ids).execute()
    
    # 3. Eliminar tareas
    client.table("ceo_tasks").delete().in_("id", task_ids).execute()
    
    return {
        "ok": True,
        "candidatas": candidatas,
        "eliminadas": candidatas,
        "dry_run": dry_run,
        "ejecutado": datetime.now(timezone.utc).isoformat()
    }
