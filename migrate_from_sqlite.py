import sqlite3
import uuid
import json
import hashlib
import os
from sqlalchemy import create_engine, text

def generate_idempotency_key(data):
    """Genera un idempotency_key a partir de los datos originales (hash SHA-256)."""
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()

def migrate(sqlite_path, supabase_url):
    # Conectar a SQLite
    sqlite_conn = sqlite3.connect(sqlite_path)
    sqlite_cursor = sqlite_conn.cursor()

    # Obtener tabla(s) a migrar (ejemplo: "old_records")
    sqlite_cursor.execute("SELECT id, user_id, data, created_at FROM old_records")
    rows = sqlite_cursor.fetchall()

    # Conectar a Supabase
    engine = create_engine(supabase_url)
    
    # Insertar en Supabase
    with engine.begin() as conn:
        for row in rows:
            old_id, user_id, data_json, created_at = row
            data = json.loads(data_json)
            idempotency_key = generate_idempotency_key(data)
            
            # Verificar si ya existe (por idempotency_key)
            existing = conn.execute(
                text("SELECT 1 FROM records WHERE idempotency_key = :key"),
                {"key": idempotency_key}
            ).first()
            if existing:
                print(f"Saltando duplicado: key {idempotency_key}")
                continue

            # Insertar registro
            new_id = uuid.uuid4()
            conn.execute(
                text("""
                    INSERT INTO records (id, idempotency_key, user_id, data, created_at)
                    VALUES (:id, :key, :uid, :data, :created_at)
                """),
                {
                    "id": new_id,
                    "key": idempotency_key,
                    "uid": user_id,
                    "data": json.dumps(data),
                    "created_at": created_at
                }
            )
            print(f"Migrado registro {old_id} -> {new_id}")

    sqlite_conn.close()
    print("Migración completada.")

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 3:
        print("Uso: python migrate_from_sqlite.py <sqlite_file> <supabase_db_url>")
        sys.exit(1)
    migrate(sys.argv[1], sys.argv[2])
