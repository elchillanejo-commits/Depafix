#!/usr/bin/env python3
"""
Sube datos/serviu_2026.json (tabla de precios referenciales SERVIU/MINVU) a
Supabase, tabla precios_serviu. Requiere que la tabla exista (ver
sql/create_precios_serviu.sql) y que .env tenga SUPABASE_URL/SUPABASE_KEY.

Uso:
    python3 subir_precios_serviu.py [--archivo datos/serviu_2026.json]
"""
import argparse
import hashlib
import json
import logging
from datetime import datetime, timezone

from core.db_manager import db

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def generar_idempotency_key(item, unidad):
    cadena = f"serviu_{item}_{unidad}"
    return hashlib.sha256(cadena.encode()).hexdigest()


def subir(archivo, fuente):
    with open(archivo, encoding="utf-8") as f:
        payload = json.load(f)
    items = payload["items"] if isinstance(payload, dict) and "items" in payload else payload

    subidos = 0
    omitidos = 0
    for row in items:
        idem = generar_idempotency_key(row["item"], row.get("unidad", ""))
        existente = db.table("precios_serviu").select("id").eq("idempotency_key", idem).execute()
        if existente.data:
            omitidos += 1
            continue
        db.table("precios_serviu").insert({
            "item": row["item"],
            "unidad": row.get("unidad"),
            "valor_unitario": row["valor_uf"],
            "fuente": fuente,
            "idempotency_key": idem,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }).execute()
        subidos += 1

    logger.info("✅ Subidos %d registros nuevos, %d ya existían.", subidos, omitidos)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--archivo", default="datos/serviu_2026.json")
    args = parser.parse_args()

    with open(args.archivo, encoding="utf-8") as f:
        payload = json.load(f)
    fuente = payload.get("meta", {}).get("url_origen", args.archivo) if isinstance(payload, dict) else args.archivo

    subir(args.archivo, fuente)


if __name__ == "__main__":
    main()
