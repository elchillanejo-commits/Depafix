#!/bin/bash
set -e
echo "🔍 Verificando DB..."
python3 -c "import os; from core.db_manager import DatabaseManager; db = DatabaseManager(os.getenv('DATABASE_URL', 'postgresql://usuario:contraseña@db.supabase.co:6543/postgres'), statement_timeout_ms=5000); db.get_connection().execute('SELECT 1').scalar()"
echo "✅ DB OK. Levantando Uvicorn..."
uvicorn core.api:app --host 0.0.0.0 --port 8000 --reload
