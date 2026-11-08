#!/usr/bin/env python3
"""Build 2 — Auditoría automática de coaches Agua/Aire/Fuego en Supabase."""
import os
import sys
import json
from pathlib import Path
from dotenv import load_dotenv
from supabase import create_client
from sentence_transformers import SentenceTransformer

load_dotenv(Path(__file__).with_name(".env"))

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")
MODELO = "intfloat/multilingual-e5-small"
UMBRAL = 0.80

COACHES = [
    ("coach_agua", "match_coach_agua", "¿cómo gestiono un equipo de trabajo?"),
    ("coach_aire", "match_coach_aire", "¿cómo ventilo una habitación correctamente?"),
    ("coach_fuego", "match_coach_fuego", "¿cómo prevengo un incendio en la cocina?"),
]

resultados = []

def main():
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("[ERROR] Faltan SUPABASE_URL y SUPABASE_SERVICE_ROLE_KEY")
        sys.exit(1)

    cliente = create_client(SUPABASE_URL, SUPABASE_KEY)
    modelo = SentenceTransformer(MODELO)

    for tabla, rpc, pregunta in COACHES:
        fila = {"coach": tabla, "rpc": rpc, "pregunta": pregunta, "estado": "❌", "detalle": ""}
        try:
            vector = modelo.encode(f"query: {pregunta}", show_progress_bar=False).tolist()
            resp = cliente.rpc(rpc, {
                "query_embedding": vector,
                "match_threshold": 0.0,
                "match_count": 3,
            }).execute()
            data = resp.data or []
            if not data:
                fila["estado"] = "❌"
                fila["detalle"] = "la tabla está vacía o sin resultados"
            else:
                top = data[0]
                sim = top.get("similarity", 0) or 0
                contenido = (top.get("contenido") or "")[:120].replace("\n", " ")
                if sim > UMBRAL:
                    fila["estado"] = "✅"
                    fila["detalle"] = f"similitud={sim:.4f} | {contenido}..."
                else:
                    fila["estado"] = "❌"
                    fila["detalle"] = f"similitud baja ({sim:.4f} <= {UMBRAL})"
        except Exception as e:
            msg = str(e)
            if "does not exist" in msg or "404" in msg or "function" in msg.lower():
                fila["detalle"] = "el RPC no existe"
            elif "relation" in msg.lower() or "table" in msg.lower():
                fila["detalle"] = "la tabla no existe"
            else:
                fila["detalle"] = f"error: {msg[:120]}"
        resultados.append(fila)

    # Reporte
    print("=" * 70)
    print("AUDITORIA COACHES AGUA / AIRE / FUEGO")
    print("=" * 70)
    for f in resultados:
        print(f"{f['estado']} {f['coach']:12} | {f['detalle']}")
    print("=" * 70)

    todos_ok = all(f["estado"] == "✅" for f in resultados)
    sys.exit(0 if todos_ok else 1)

if __name__ == "__main__":
    main()
