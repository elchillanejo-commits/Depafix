#!/usr/bin/env python3
\"\"\"
Servicio sancho - DepaFix Cloud Native
\"\"\"
import os
from fastapi import FastAPI, Request
import psycopg2
from datetime import datetime

app = FastAPI(title="DepaFix - sancho", version="1.0.0")

DB_CONFIG = {
    "host": os.getenv("PGHOST", "postgres"),
    "port": os.getenv("PGPORT", "5432"),
    "dbname": os.getenv("PGDATABASE", "depafix"),
    "user": os.getenv("PGUSER", "depafix"),
    "password": os.getenv("PGPASSWORD", "sGXizxWs4khbF8ZJeOJ")
}

@app.get("/health")
def health():
    return {"status": "ok", "service": "sancho", "timestamp": datetime.now().isoformat()}

@app.get("/")
def root():
    return {"service": "sancho", "status": "running", "version": "1.0.0"}

@app.get("/metrics")
def metrics():
    # Conexión a BD para métricas básicas
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        cur.execute("SELECT 1")
        db_status = "connected"
        cur.close()
        conn.close()
    except:
        db_status = "disconnected"
    return {
        "service": "sancho",
        "db": db_status,
        "uptime": "running",
        "timestamp": datetime.now().isoformat()
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
