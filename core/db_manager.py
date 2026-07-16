import os
from dotenv import load_dotenv
from supabase import create_client, Client
from typing import Optional

load_dotenv()

class DatabaseManager:
    _client: Optional[Client] = None
    _service_client: Optional[Client] = None

    @classmethod
    def get_client(cls) -> Client:
        """Cliente 'anon' -- el que usa todo el proyecto por defecto. RLS
        limita lo que puede leer/escribir (a propósito: ver
        sql/create_velas_cripto.sql). No usar este método para escrituras
        que necesiten bypassear RLS -- para eso está get_service_client()."""
        if cls._client is None:
            url = os.getenv("SUPABASE_URL")
            key = os.getenv("SUPABASE_KEY")
            if not url or not key or url == "TU_URL_REAL_AQUI":
                raise RuntimeError("Credenciales de Supabase no configuradas en .env")
            cls._client = create_client(url, key)
        return cls._client

    @classmethod
    def get_service_client(cls) -> Client:
        """Cliente con la service_role key -- bypassea RLS por diseño de
        Supabase. Usar SOLO server-side, para escrituras confiables como
        src/trading/data_pipeline.py (nunca para nada que sirva una request
        de un cliente/frontend). Requiere SUPABASE_SERVICE_ROLE_KEY en .env
        (acepta también SUPABASE_SERVICE_KEY por compatibilidad), obtenida
        del dashboard de Supabase (Settings -> API -> service_role); no es
        la misma key que SUPABASE_KEY (esa es la anon, pública).

        Valida la forma de JWT (3 segmentos separados por punto, empieza con
        'eyJ') antes de crear el cliente -- un valor placeholder o corrupto
        falla acá, con un mensaje claro, en vez de fallar más adelante con un
        error críptico de autenticación de Supabase en medio del pipeline."""
        if cls._service_client is None:
            url = os.getenv("SUPABASE_URL")
            key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_KEY")
            if not url or not key:
                raise RuntimeError(
                    "SUPABASE_SERVICE_ROLE_KEY no configurada en .env -- sacala del dashboard "
                    "de Supabase (Settings > API > service_role) y agregala a .env. "
                    "No uses la anon key acá: RLS la bloquea a propósito."
                )
            if not key.startswith("eyJ") or key.count(".") != 2:
                raise RuntimeError(
                    "SUPABASE_SERVICE_ROLE_KEY está configurada pero no tiene forma de JWT "
                    "válido (debería empezar con 'eyJ' y tener 3 segmentos separados por "
                    "punto, ~200+ caracteres) -- parece un placeholder o un valor corrupto. "
                    "Reemplazala con la key real de Settings > API > service_role."
                )
            cls._service_client = create_client(url, key)
        return cls._service_client


db = DatabaseManager.get_client()
