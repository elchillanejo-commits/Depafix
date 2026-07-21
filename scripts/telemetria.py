import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

ESTADOS_VALIDOS = {"online", "offline", "error", "warning"}
_MAPEO_ESTADO = {"operativo": "online", "ok": "online"}


def reportar_salud(agente, status, detalles):
    estado = _MAPEO_ESTADO.get(status.lower(), status.lower())
    if estado not in ESTADOS_VALIDOS:
        estado = "warning"

    supabase = create_client(os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_SERVICE_ROLE_KEY"))
    supabase.table("salud_agentes").insert({
        "agente": agente,
        "estado": estado,
        "mensaje": detalles,
    }).execute()
