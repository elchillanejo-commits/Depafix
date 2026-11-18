import asyncio
import os
from dotenv import load_dotenv
from supabase import create_async_client

load_dotenv()

async def escanear_supabase():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    
    print("==================================================")
    print("🔍 [PROFESOR SUPABASE] Iniciando escáner de auditoría...")
    print("==================================================")
    
    if not url or not key:
        print("❌ Error crítico: Faltan credenciales en el .env")
        return

    try:
        client = await create_async_client(url, key)
        print("🟢 Conexión asíncrona establecida con éxito.")
        
        # Test 1: Verificar tabla cotizaciones
        response = await client.table("cotizaciones").select("id", count="exact").limit(1).execute()
        print(f"🟢 Tabla 'cotizaciones' accesible. Registros encontrados: {response.count if hasattr(response, 'count') else 'OK'}")
        
    except Exception as e:
        print(f"🔴 Alerta en el escáner de Supabase: {str(e)}")
    print("==================================================")

if __name__ == "__main__":
    asyncio.run(escanear_supabase())
