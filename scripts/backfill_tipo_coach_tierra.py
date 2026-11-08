#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Backfill de metadata.tipo en coach_tierra para filas origen='serviu'.

Reclasifica cada fragmento con el Profesor de Tierra (profesores/tierra.md)
y actualiza metadata.tipo por id:
  CALCULO              -> calculo
  EJEMPLOS DE COTIZACION -> cotizacion
  NORMATIVA            -> normativa
  BASURA               -> basura

Idempotente: solo procesa filas que aún no tienen metadata.tipo.

Uso:
  python scripts/backfill_tipo_coach_tierra.py --dry-run
  python scripts/backfill_tipo_coach_tierra.py --lote 5
"""

import argparse
import json
import os
import sys
import time
import unicodedata
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI
from supabase import create_client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip()
SUPABASE_KEY = (
    os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    or os.getenv("SUPABASE_KEY", "").strip()
)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
PROMPT_FILE = Path("profesores/tierra.md")

if not SUPABASE_URL or not SUPABASE_KEY or not OPENAI_API_KEY:
    print("[ERROR] Faltan SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY / OPENAI_API_KEY")
    sys.exit(1)
if not PROMPT_FILE.exists():
    print(f"[ERROR] No existe {PROMPT_FILE}")
    sys.exit(1)

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
client = OpenAI(api_key=OPENAI_API_KEY)
SYSTEM_PROMPT = PROMPT_FILE.read_text(encoding="utf-8")


def sin_acentos(texto: str) -> str:
    texto = unicodedata.normalize("NFD", texto)
    return "".join(c for c in texto if unicodedata.category(c) != "Mn")


def normalizar_categoria(valor: str) -> str:
    n = sin_acentos(str(valor)).upper().strip()
    if n.startswith("CALCULO"):
        return "calculo"
    if "COTIZACION" in n:
        return "cotizacion"
    if n.startswith("NORMATIVA"):
        return "normativa"
    if n.startswith("BASURA"):
        return "basura"
    return n.lower() or "basura"


def clasificar_lote(fragmentos, reintentos=3):
    texto_lote = "\n\n---\n\n".join(
        f"FRAGMENTO {i + 1}:\n{f[:1500]}" for i, f in enumerate(fragmentos)
    )
    prompt = (
        f"Clasifica los siguientes {len(fragmentos)} fragmentos. "
        "Devuelve SOLO un JSON con un array 'resultados', donde cada elemento "
        "tenga la clave 'clasificacion'.\n\n" + texto_lote
    )
    for intento in range(1, reintentos + 1):
        try:
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.0,
            )
            return json.loads(resp.choices[0].message.content).get("resultados", [])
        except Exception as error:
            print(f"    [WARN] lote falló (intento {intento}/{reintentos}): {str(error)[:120]}")
            time.sleep(2 * intento)
    return [{"clasificacion": "BASURA"} for _ in fragmentos]


def fetch_filas_serviu():
    filas = []
    start = 0
    while True:
        r = (
            supabase.table("coach_tierra")
            .select("id,contenido,metadata")
            .filter("metadata->>origen", "eq", "serviu")
            .range(start, start + 999)
            .execute()
        )
        if not r.data:
            break
        filas.extend(r.data)
        if len(r.data) < 1000:
            break
        start += 1000
    return filas


def metadata_dict(fila):
    m = fila.get("metadata") or {}
    if isinstance(m, str):
        try:
            m = json.loads(m)
        except (TypeError, ValueError):
            m = {}
    return m if isinstance(m, dict) else {}


def main():
    parser = argparse.ArgumentParser(description="Backfill metadata.tipo en coach_tierra (origen=serviu)")
    parser.add_argument("--dry-run", action="store_true", help="Solo cuenta pendientes, no actualiza")
    parser.add_argument("--lote", type=int, default=5, help="Fragmentos por llamada a OpenAI (default 5)")
    args = parser.parse_args()

    print("[1/3] Leyendo filas origen=serviu de coach_tierra...")
    filas = fetch_filas_serviu()
    pendientes = [(f, metadata_dict(f)) for f in filas]
    pendientes = [(f, m) for f, m in pendientes if not m.get("tipo")]
    print(f"      total serviu      : {len(filas)}")
    print(f"      sin metadata.tipo : {len(pendientes)}")

    if args.dry_run:
        print("[DRY-RUN] No se actualiza nada.")
        return
    if not pendientes:
        print("[OK] No hay filas pendientes.")
        return

    print(f"[2/3] Reclasificando en lotes de {args.lote}...")
    conteo = {"calculo": 0, "cotizacion": 0, "normativa": 0, "basura": 0, "otro": 0}
    total = len(pendientes)
    for i in range(0, total, args.lote):
        lote = pendientes[i : i + args.lote]
        clasificaciones = clasificar_lote([f["contenido"] for f, _ in lote])
        for (fila, meta), clas in zip(lote, clasificaciones):
            tipo = normalizar_categoria(clas.get("clasificacion", "BASURA"))
            if tipo not in conteo:
                conteo["otro"] += 1
            else:
                conteo[tipo] += 1
            nueva = dict(meta)
            nueva["tipo"] = tipo
            supabase.table("coach_tierra").update({"metadata": nueva}).eq("id", fila["id"]).execute()
        procesados = min(i + args.lote, total)
        print(f"      {procesados}/{total} | calculo={conteo['calculo']} cotizacion={conteo['cotizacion']} "
              f"normativa={conteo['normativa']} basura={conteo['basura']} otro={conteo['otro']}")

    print("[3/3] Backfill completado.")
    print(f"      {conteo}")


if __name__ == "__main__":
    main()
