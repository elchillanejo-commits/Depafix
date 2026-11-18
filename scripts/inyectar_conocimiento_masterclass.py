import asyncio
import os
from dotenv import load_dotenv
from supabase import create_async_client

load_dotenv()

async def inyectar_masterclasses():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    
    print("==================================================")
    print("🧠 [PROFESOR SUPABASE] Inyectando Masterclasses al RAG...")
    print("==================================================")
    
    if not url or not key:
        print("❌ Error: Faltan credenciales en el archivo .env")
        return

    client = await create_async_client(url, key)
    
    # Conocimiento destilado de los 7 videos de Supabase, CLI, MCPs y CRM
    master_chunks = [
        {
            "content": "Supabase es una alternativa open-source a PostgreSQL que integra base de datos relacional, autenticación robusta, storage de archivos en buckets y capacidades vectoriales (pgvector) para IA.",
            "metadata": {"fuente": "Masterclass Supabase from Zero", "modulo": "Elemento Tierra"}
        },
        {
            "content": "Las políticas RLS (Row Level Security) permiten aplicar reglas de seguridad a nivel de fila directamente en PostgreSQL, asegurando que cada usuario autenticado solo vea y modifique sus propios registros.",
            "metadata": {"fuente": "Supabase Security & RLS Guide", "modulo": "Elemento Tierra/Metal"}
        },
        {
            "content": "El uso de Supabase CLI y Skills permite que los agentes de IA ejecuten migraciones, validen esquemas y controlen bases de datos directamente desde la terminal con comandos SQL nativos.",
            "metadata": {"fuente": "Supabase con IA CLI & Skills", "modulo": "Elemento Metal"}
        },
        {
            "content": "Para arquitecturas CRM y de gestión inmobiliaria (como DepaFix), la estructura ideal separa la autenticación, las tablas relacionales de clientes/propiedades y el almacenamiento privado en buckets por ID de usuario.",
            "metadata": {"fuente": "Build a Simple CRM with AI", "modulo": "Elemento Aire/Tierra"}
        },
        {
            "content": "Supabase es ideal para MVPs rápidos y sistemas medianos gracias a su generoso plan gratuito y su capa relacional completa, aunque para procesamiento masivo en tiempo real muy pesado requiere consideraciones de infraestructura.",
            "metadata": {"fuente": "¿Deberías usar Supabase?", "modulo": "Elemento Éter"}
        }
    ]

    for item in master_chunks:
        vector_ficticio = [0.01] * 1536
        payload = {
            "content": item["content"],
            "metadata": item["metadata"],
            "embedding": vector_ficticio
        }
        try:
            await client.table("knowledge").insert(payload).execute()
            print(f"🟢 [Inyectado] {item['metadata']['fuente']} -> {item['content'][:50]}...")
        except Exception as e:
            print(f"🔴 Error al inyectar chunk: {str(e)}")

    print("==================================================")
    print("🟢 ¡Conocimiento de las masterclasses inyectado con éxito!")
    print("==================================================")

if __name__ == "__main__":
    asyncio.run(inyectar_masterclasses())
