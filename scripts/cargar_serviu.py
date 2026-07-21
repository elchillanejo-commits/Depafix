#!/usr/bin/env python3
"""
Carga manual de datos SERVIU desde JSON a Supabase.
Ejecutar después de que Claude genere ~/Proyectos/DepaFix/datos/serviu_2026.json
"""
import json, sys
from pathlib import Path
sys.path.insert(0, "/home/ibar/Proyectos/02_PROCURADOR")  # reorg 2026-07-19: core/ movido fuera de DepaFix
from core.db_manager import db

def cargar():
    json_path = Path("datos/serviu_2026.json")
    if not json_path.exists():
        print(f"❌ No existe {json_path}. Espera a que Claude termine.")
        return
    with open(json_path) as f:
        data = json.load(f)
    if not data:
        print("❌ JSON vacío.")
        return
    print(f"📊 Cargando {len(data)} registros...")
    for item in data:
        try:
            row = {
                "item": item.get("item"),
                "unidad": item.get("unidad"),
                "valor_unitario": item.get("valor_uf") or item.get("valor"),
                "fuente": "SERVIU_DS27_RM_2026",
                "idempotency_key": f"serviu_{item.get('item')}"
            }
            db.table("precios_serviu").upsert(row, on_conflict="idempotency_key").execute()
        except Exception as e:
            print(f"⚠️ Error con {item}: {e}")
    print("✅ Carga completada.")

if __name__ == "__main__":
    cargar()
