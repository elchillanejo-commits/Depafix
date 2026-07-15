import os
from dotenv import load_dotenv
from supabase import create_client, Client
from typing import Optional

load_dotenv()

class DatabaseManager:
    _client: Optional[Client] = None

    @classmethod
    def get_client(cls) -> Client:
        if cls._client is None:
            url = os.getenv("SUPABASE_URL")
            key = os.getenv("SUPABASE_KEY")
            if not url or not key or url == "TU_URL_REAL_AQUI":
                raise RuntimeError("Credenciales de Supabase no configuradas en .env")
            cls._client = create_client(url, key)
        return cls._client


db = DatabaseManager.get_client()
