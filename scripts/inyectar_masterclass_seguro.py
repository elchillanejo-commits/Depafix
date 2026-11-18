import asyncio
import os
from dotenv import load_dotenv
from supabase import create_async_client

load_dotenv()

async def run():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    client = await create_async_client(url, key)
    
    chunks = [
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
        }
    ]

    for item in chunks:
        res = await client.table("knowledge").insert({
            "content": item["content"],
            "metadata": item["metadata"],
            "embedding": [0.01] * 1536
        }).execute()
        print(f"🟢 Inyectado: {item['metadata']['fuente']}")

if __name__ == "__main__":
    asyncio.run(run())
