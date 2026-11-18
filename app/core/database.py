import os
from typing import Optional
from supabase import create_async_client, AsyncClient
from dotenv import load_dotenv

load_dotenv()

class Database:
    _client: Optional[AsyncClient] = None

    @classmethod
    async def get_client(cls) -> AsyncClient:
        if cls._client is None:
            url = os.getenv("SUPABASE_URL")
            key = os.getenv("SUPABASE_KEY")
            if not url or not key:
                raise ValueError("Faltan SUPABASE_URL o SUPABASE_KEY.")
            cls._client = await create_async_client(url, key)
        return cls._client

async def get_db() -> AsyncClient:
    return await Database.get_client()
