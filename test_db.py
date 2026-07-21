import sys
sys.path.insert(0, "/home/ibar/Proyectos/02_PROCURADOR")  # reorg 2026-07-19: core/ movido fuera de DepaFix
from DepaFix.core.db_manager import DatabaseManager
DB_URL = "postgresql://usuario:contraseña@db.supabase.co:6543/postgres"  # CAMBIAR
try:
    db = DatabaseManager(DB_URL, statement_timeout_ms=5000)
    with db.get_connection() as conn:
        print("✅ Fecha:", conn.execute("SELECT NOW()").scalar())
except Exception as e:
    print("❌ Error:", e)
