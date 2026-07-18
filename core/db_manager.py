"""
Database Manager - Centraliza conexiones a Supabase
Reglas de oro: telemetría, retry, manejo de errores.
"""
import os
import time
from supabase import create_client

class DatabaseManager:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self.url = os.getenv('SUPABASE_URL')
        self.anon_key = os.getenv('SUPABASE_KEY')
        self.service_key = os.getenv('SUPABASE_SERVICE_ROLE_KEY') or os.getenv('SUPABASE_KEY')
        if not self.url or not self.service_key:
            raise ValueError("Faltan SUPABASE_URL o SUPABASE_SERVICE_ROLE_KEY")
        self._initialized = True
    
    def get_client(self, use_service_role=False):
        """Retorna cliente Supabase con anon o service_role."""
        key = self.service_key if use_service_role else self.anon_key
        return create_client(self.url, key)
    
    def get_service_client(self):
        """Retorna cliente con service_role (bypassea RLS)."""
        return self.get_client(use_service_role=True)
    
    def get_anon_client(self):
        """Retorna cliente con anon key (respeta RLS)."""
        return self.get_client(use_service_role=False)

# Singleton
db_manager = DatabaseManager()
