import os
from supabase import create_client, Client

# Variables de entorno o credenciales directas de tu proyecto Supabase
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://TU-PROYECTO.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "TU-ANON-KEY")

def inicializar_supabase() -> Client:
    try:
        return create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as e:
        print(f"❌ Error al inicializar Supabase: {e}")
        return None

def registrar_presupuesto(codigo_partida, comuna, magnitud, total_final):
    supabase = inicializar_supabase()
    if not supabase:
        return False

    payload = {
        "codigo_partida": codigo_partida,
        "comuna": comuna,
        "magnitud": magnitud,
        "total_final": total_final,
        "estado": "generado"
    }

    try:
        # Asume que existe una tabla llamada 'presupuestos_tierra'
        respuesta = supabase.table("presupuestos_tierra").insert(payload).execute()
        print(f"☁️ POST exitoso: Presupuesto registrado en Supabase.")
        return True
    except Exception as e:
        print(f"❌ Error en POST a Supabase: {e}")
        return False

if __name__ == "__main__":
    print("=== CONECTOR SUPABASE DEPAFIX (MODO OBRA GRUESA) ===")
    print("Módulo listo para ser importado en generar_ppto.py")
