"""
Database Manager - Centraliza conexiones a Supabase.

Soporta las dos convenciones de uso que coexisten en el repo:
    DatabaseManager.get_client()        (classmethod -- ~10 call sites historicos:
                                          main.py, trade_agent.py, trading_orchestrator.py, etc.)
    db.get_client() / db_manager.get_client()   (sobre la instancia singleton)

Ambas resuelven al mismo metodo: un @classmethod tambien responde
correctamente cuando se llama sobre una instancia (Python resuelve `cls`
al tipo real del objeto). No hay que duplicar la logica en un metodo de
instancia y un classmethod con el mismo nombre -- esa duplicacion fue
justamente un bug real que se detecto en el chat: la segunda definicion
pisaba la primera y terminaba en RecursionError/TypeError.
"""
import os
from dotenv import load_dotenv
from supabase import create_client, Client
from typing import Optional

load_dotenv()


class DatabaseManager:
    _instance: Optional["DatabaseManager"] = None
    _client: Optional[Client] = None
    _service_client: Optional[Client] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self.url = os.getenv("SUPABASE_URL")
        self.anon_key = os.getenv("SUPABASE_KEY")
        self.service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_KEY")
        if not self.url:
            raise RuntimeError("SUPABASE_URL no configurada en .env")
        self._initialized = True

    @classmethod
    def get_client(cls) -> Client:
        """Cliente 'anon' -- el que usa la mayoria del proyecto por defecto.
        RLS limita lo que puede leer/escribir a proposito."""
        self = cls()
        if self._client is None:
            if not self.anon_key:
                raise RuntimeError("SUPABASE_KEY no configurada en .env")
            self._client = create_client(self.url, self.anon_key)
        return self._client

    @classmethod
    def get_service_client(cls) -> Client:
        """Cliente con service_role -- bypassea RLS por diseno de Supabase.
        Usar solo server-side. Nunca cae en silencio a la anon key: si el
        service key falta o no tiene forma de JWT, falla fuerte aca (con
        mensaje claro) en vez de escribir mas adelante con permisos
        insuficientes o, peor, exponer datos protegidos por RLS."""
        self = cls()
        if self._service_client is None:
            if not self.service_key:
                raise RuntimeError(
                    "SUPABASE_SERVICE_ROLE_KEY no configurada en .env -- sacala del "
                    "dashboard de Supabase (Settings > API > service_role) y agregala "
                    "a .env. No uses la anon key aca: RLS la bloquea a proposito."
                )
            if not self.service_key.startswith("eyJ") or self.service_key.count(".") != 2:
                raise RuntimeError(
                    "SUPABASE_SERVICE_ROLE_KEY esta configurada pero no tiene forma de "
                    "JWT valido (deberia empezar con 'eyJ' y tener 3 segmentos separados "
                    "por punto) -- parece un placeholder o un valor corrupto."
                )
            self._service_client = create_client(self.url, self.service_key)
        return self._service_client

    @classmethod
    def get_anon_client(cls) -> Client:
        """Alias explicito de get_client() -- mismo cliente anon."""
        return cls.get_client()


# Singletons para imports legacy: distintos archivos del repo importan
# 'db' (api.py, predict_logic.py, scripts/cargar_serviu.py,
# subir_precios_serviu.py) o 'db_manager' (core/procurador_tool.py) --
# ambos apuntan al mismo objeto, no hace falta elegir uno.
db_manager = DatabaseManager()
db = db_manager
