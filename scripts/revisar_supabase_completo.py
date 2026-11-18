import asyncio
import os
from dotenv import load_dotenv
from supabase import create_async_client

load_dotenv()

async def revision_profunda():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    
    print("==================================================")
    print("🔍 [AUDITORÍA SUPABASE] Radiografía Total - DepaFix 3.0")
    print("==================================================")
    
    if not url or not key:
        print("❌ Error: Faltan credenciales en el archivo .env")
        return

    try:
        client = await create_async_client(url, key)
        print("🟢 Conexión asíncrona establecida con éxito.\n")
        
        # Lista de tablas core a auditar
        tablas = ["cotizaciones", "knowledge", "propiedades", "clientes", "items"]
        
        for tabla in tablas:
            try:
                res = await client.table(tabla).select("*", count="exact").limit(3).execute()
                count = res.count if hasattr(res, 'count') else len(res.data)
                print(f"📁 Tabla [{tabla}]:")
                print(f"   ├─ Estado: 🟢 Accesible")
                print(f"   ├─ Registros totales: {count}")
                if res.data:
                    print(f"   └─ Muestra último registro: {res.data[0]}")
                else:
                    print(f"   └─ Muestra: (Tabla vacía)")
                print("-" * 50)
            except Exception as e:
                print(f"📁 Tabla [{tabla}]: 🔴 No accesible o no creada aún ({str(e)})")
                print("-" * 50)

        print("🟢 Auditoría de Supabase finalizada.")
        
    except Exception as e:
        print(f"🔴 Error crítico conectando a Supabase: {str(e)}")
    print("==================================================")

if __name__ == "__main__":
    asyncio.run(revision_profunda())
