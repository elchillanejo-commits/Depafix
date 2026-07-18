import logging
from datetime import datetime
from supabase import create_client
import os
from dotenv import load_dotenv

load_dotenv()
supabase = create_client(os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_KEY"))

def log_compliance(client_id, action, status, details=""):
    """Registra la actividad de auditoría para el Procurador."""
    try:
        log_entry = {
            "client_id": client_id,
            "action": action,
            "status": status,
            "details": details,
            "created_at": datetime.utcnow().isoformat()
        }
        supabase.table("compliance_logs").insert(log_entry).execute()
        print(f"[PROCURADOR] Log registrado: {action} - {status}")
    except Exception as e:
        print(f"[PROCURADOR ERROR] No se pudo registrar: {e}")

if __name__ == "__main__":
    # Ejemplo de uso tras la validación de un cliente
    log_compliance("test_id_001", "KYC_VERIFICATION", "PASSED", "Documentación recibida y validada")
