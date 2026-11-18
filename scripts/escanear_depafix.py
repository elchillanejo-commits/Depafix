import asyncio
import os
from dotenv import load_dotenv
from supabase import create_async_client

load_dotenv()

async def escaneo_profundo():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    
    print("==================================================")
    print("🛡️ [PROFESOR SUPABASE] Auditoría Integral - DepaFix 3.0")
    print("==================================================")
    
    if not url or not key:
        print("❌ Error crítico: Faltan credenciales en el archivo .env")
        return

    try:
        client = await create_async_client(url, key)
        print("🟢 Conexión asíncrona establecida con Supabase.")
        
        # 1. Auditoría de Cotizaciones
        res_cot = await client.table("cotizaciones").select("id", count="exact").execute()
        print(f"📊 Tabla [cotizaciones]: {res_cot.count if hasattr(res_cot, 'count') else 'OK'} registros encontrados.")

        # 2. Auditoría de la Base de Conocimiento RAG (Vectorial)
        try:
            res_rag = await client.table("knowledge").select("id", count="exact").execute()
            print(f"🧠 Tabla [knowledge / pgvector]: {res_rag.count if hasattr(res_rag, 'count') else 'OK'} fragmentos indexados.")
        except Exception:
            print("⚠️ Tabla [knowledge] no detectada aún (pendiente de migración RAG).")

        print("🟢 Auditoría completada con éxito. El radier está firme.")
        
    except Exception as e:
        print(f"🔴 Error crítico en el escáner: {str(e)}")
    print("==================================================")

if __name__ == "__main__":
    asyncio.run(escaneo_profundo())
