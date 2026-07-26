#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Database Manager - Conexión a Supabase centralizada.
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from supabase import create_client, Client

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / '.env'

if ENV_PATH.exists():
    load_dotenv(ENV_PATH)
else:
    print(f"⚠️ No se encontró .env en {ENV_PATH}")
    sys.exit(1)

class DatabaseManager:
    _client = None
    
    @classmethod
    def get_client(cls) -> Client:
        if cls._client is None:
            url = os.getenv('SUPABASE_URL')
            key = os.getenv('SUPABASE_KEY')
            if not url or not key:
                raise ValueError(f"Faltan SUPABASE_URL o SUPABASE_KEY en .env")
            cls._client = create_client(url, key)
        return cls._client
    
    _service_client = None

    @classmethod
    def get_service_client(cls) -> Client:
        """Cliente con la service_role key -- bypassea RLS por diseño de
        Supabase. Requiere SUPABASE_SERVICE_ROLE_KEY en .env (acepta también
        SUPABASE_SERVICE_KEY por compatibilidad). Valida forma de JWT antes de
        crear el cliente para fallar explícito acá en vez de con un error
        críptico de autenticación más adelante."""
        if cls._service_client is None:
            url = os.getenv('SUPABASE_URL')
            key = os.getenv('SUPABASE_SERVICE_ROLE_KEY') or os.getenv('SUPABASE_SERVICE_KEY')
            if not url or not key:
                raise RuntimeError(
                    "Falta SUPABASE_SERVICE_ROLE_KEY en .env -- sacala del dashboard "
                    "de Supabase (Settings > API > service_role)."
                )
            if not key.startswith("eyJ") or key.count(".") != 2:
                raise RuntimeError(
                    "SUPABASE_SERVICE_ROLE_KEY no tiene forma de JWT válido -- "
                    "parece un placeholder o valor corrupto."
                )
            cls._service_client = create_client(url, key)
        return cls._service_client

# Instancia global
db = DatabaseManager.get_client()

if __name__ == '__main__':
    print("✅ Database Manager inicializado correctamente")
