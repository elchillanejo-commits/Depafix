#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Database Manager - Conexión a Supabase centralizada.
Versión para Railway (usa variables de entorno directamente).
"""
import os
import sys
from pathlib import Path
from supabase import create_client, Client

# Intentar cargar .env solo si existe (local)
try:
    from dotenv import load_dotenv
    BASE_DIR = Path(__file__).resolve().parent.parent
    ENV_PATH = BASE_DIR / '.env'
    if ENV_PATH.exists():
        load_dotenv(ENV_PATH)
        print(f"✅ .env cargado desde {ENV_PATH}")
except ImportError:
    pass

class DatabaseManager:
    _client = None
    _service_client = None
    
    @classmethod
    def get_client(cls) -> Client:
        if cls._client is None:
            url = os.getenv('SUPABASE_URL')
            key = os.getenv('SUPABASE_KEY')
            if not url or not key:
                raise ValueError("Faltan SUPABASE_URL o SUPABASE_KEY en variables de entorno")
            cls._client = create_client(url, key)
            print("✅ Cliente Supabase (anon) inicializado")
        return cls._client
    
    @classmethod
    def get_service_client(cls) -> Client:
        if cls._service_client is None:
            url = os.getenv('SUPABASE_URL')
            key = os.getenv('SUPABASE_SERVICE_ROLE_KEY') or os.getenv('SUPABASE_KEY')
            if not url or not key:
                raise ValueError("Faltan SUPABASE_URL o SUPABASE_SERVICE_ROLE_KEY en variables de entorno")
            cls._service_client = create_client(url, key)
            print("✅ Cliente Supabase (service_role) inicializado")
        return cls._service_client

# Instancia global
db = None
try:
    db = DatabaseManager.get_client()
    print("✅ Database Manager inicializado correctamente")
except Exception as e:
    print(f"⚠️ Error al inicializar Database Manager: {e}")

if __name__ == '__main__':
    print("✅ Database Manager listo")
