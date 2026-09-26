import os
import pandas as pd
from datetime import datetime, timedelta, timezone
from supabase import create_client

async def analizar_tendencias_worker(params: dict) -> dict:
    dias = params.get("dias", 30)
    activo = params.get("activo")
    
    client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_ROLE_KEY"))
    
    fecha_inicio = (datetime.now(timezone.utc) - timedelta(days=dias)).isoformat()
    
    query = client.table("operaciones_ejecutadas").select("*").gte("timestamp", fecha_inicio)
    if activo:
        query = query.eq("activo", activo)
        
    data = query.execute().data
    if not data:
        return {"ok": True, "total_señales": 0, "insight": "Sin datos"}
        
    df = pd.DataFrame(data)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    por_hora = df['timestamp'].dt.strftime('%H').value_counts().sort_index().to_dict()
    por_dia = df['timestamp'].dt.day_name().value_counts().to_dict()
    distribucion = df['senal'].value_counts().to_dict()
    
    total = len(df)
    compra_pct = distribucion.get('COMPRA', 0) / total
    insight = f"Total {total} señales. "
    if compra_pct > 0.6:
        insight += "Sesgo alcista detectado."
    elif compra_pct < 0.4:
        insight += "Sesgo bajista detectado."
    else:
        insight += "Mercado neutral."
        
    return {
        "ok": True,
        "periodo": f"{dias} días",
        "total_señales": total,
        "por_hora_del_dia": por_hora,
        "por_dia_semana": por_dia,
        "distribucion_senal": distribucion,
        "insight": insight,
        "ejecutado": datetime.now(timezone.utc).isoformat()
    }
