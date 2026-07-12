#!/usr/bin/env python3
"""
Migración de datos SQLite → Supabase con claves de idempotencia.
"""
import sqlite3
import hashlib
import logging
from datetime import datetime
from core.db_manager import DatabaseManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

SQLITE_DB = "presupuestos.db"   # Asegurate de que esté en la raíz del proyecto

def generar_idempotency_key(*args) -> str:
    cadena = "_".join(str(a) for a in args)
    return hashlib.sha256(cadena.encode()).hexdigest()

def migrar_apu(cur, supabase):
    logger.info("📦 Migrando APU → apu_items...")
    cur.execute("SELECT material, unidad, precio FROM apu")
    for material, unidad, precio in cur.fetchall():
        idem = generar_idempotency_key("apu", material, unidad)
        existing = supabase.table("apu_items").select("id").eq("idempotency_key", idem).execute()
        if existing.data:
            continue
        supabase.table("apu_items").insert({
            "material": material, "unidad": unidad, "precio": precio,
            "idempotency_key": idem, "created_at": datetime.utcnow().isoformat()
        }).execute()
    logger.info("✅ APU migrado.")

def migrar_presupuestos(cur, supabase):
    logger.info("📦 Migrando presupuestos → budgets...")
    cur.execute("SELECT id, cliente, tarea, maestro, fecha, total, m2, estado, descripcion, incluye_materiales FROM presupuestos")
    for (pid, cliente, tarea, maestro, fecha, total, m2, estado, desc, inc_mat) in cur.fetchall():
        idem = generar_idempotency_key("budget", cliente or "", tarea or "", maestro or "", str(fecha), str(total), str(m2), desc or "")
        existing = supabase.table("budgets").select("id").eq("idempotency_key", idem).execute()
        if existing.data:
            continue
        resp = supabase.table("budgets").insert({
            "cliente": cliente, "tarea": tarea, "maestro": maestro,
            "fecha": fecha, "total": total, "m2": m2,
            "estado": estado, "descripcion": desc,
            "incluye_materiales": bool(inc_mat),
            "idempotency_key": idem, "created_at": datetime.utcnow().isoformat()
        }).execute()
        if not resp.data:
            continue
        new_id = resp.data[0]["id"]
        migrar_partidas(cur, supabase, pid, new_id)

def migrar_partidas(cur, supabase, old_pid, new_bid):
    cur.execute("SELECT id, cantidad, material, unidad, precio_unitario FROM partidas WHERE presupuesto_id = ?", (old_pid,))
    for (part_id, cantidad, material, unidad, precio) in cur.fetchall():
        es_labor = ("mano de obra" in material.lower() or unidad in ("jornal", "hh", "hr"))
        tabla = "labor" if es_labor else "items"
        idem = generar_idempotency_key("partida", old_pid, part_id, material, unidad, str(cantidad))
        existing = supabase.table(tabla).select("id").eq("idempotency_key", idem).execute()
        if existing.data:
            continue
        supabase.table(tabla).insert({
            "budget_id": new_bid, "cantidad": cantidad,
            "material": material, "unidad": unidad,
            "precio_unitario": precio,
            "idempotency_key": idem, "created_at": datetime.utcnow().isoformat()
        }).execute()

def main():
    logger.info("🔁 Iniciando migración SQLite → Supabase")
    sql_conn = sqlite3.connect(SQLITE_DB)
    cur = sql_conn.cursor()
    supabase = DatabaseManager.get_client()
    migrar_apu(cur, supabase)
    migrar_presupuestos(cur, supabase)
    sql_conn.close()
    logger.info("🏁 Migración completada.")

if __name__ == "__main__":
    main()
