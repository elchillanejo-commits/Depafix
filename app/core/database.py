import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from supabase import AsyncClient, create_async_client

BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env")


class Database:
    _client: Optional[AsyncClient] = None

    @classmethod
    async def get_client(cls) -> AsyncClient:
        if cls._client is None:
            url = os.getenv("SUPABASE_URL")
            # Cliente de servidor: match_knowledge_v2 no está ejecutable con
            # la clave publishable/anon. Nunca exponer esta clave al frontend.
            key = (
                os.getenv("SUPABASE_DB_KEY")
                or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
                or os.getenv("SUPABASE_KEY")
            )
            if not url or not key:
                raise ValueError(
                    "Faltan SUPABASE_URL y una clave de servidor "
                    "(SUPABASE_DB_KEY, SUPABASE_SERVICE_ROLE_KEY o SUPABASE_KEY)."
                )
            cls._client = await create_async_client(url, key)
        return cls._client

async def get_db() -> AsyncClient:
    return await Database.get_client()
