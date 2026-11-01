#!/usr/bin/env python3
"""Batch RAG DepaFix: genera un speech por prospecto usando la Mente 360.

Ejecución (desde cualquier carpeta):
    .venv/bin/python scripts/batch_rag.py            # 5 primeros prospectos
    .venv/bin/python scripts/batch_rag.py --limite 1 # prueba con 1 solo
"""

import argparse
import builtins
import csv
import os
import sys
from pathlib import Path

# 1. Permitimos importar mente_360.py del proyecto raíz cuando este
#    archivo corre subdirectorio abajo (scripts/).
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

# 2. mente_360.py resuelve ./data/*.faiss, ./profesores y ./coaches
#    relativos al CWD; fijamos el CWD al proyecto raíz para que no importe
#    desde dónde se ejecute.
os.chdir(BASE_DIR)

# 3. Si algo llegara a pedir input(), respondemos "salir" para no quedarnos colgados.
builtins.input = lambda *args, **kwargs: "salir"

from dotenv import load_dotenv  # noqa: E402
from mente_360 import cargar_cerebros, consultar_mente_360  # noqa: E402

load_dotenv(BASE_DIR / ".env")

COLUMNA_SPEECH = "speech_generado"
COLUMNA_ESTADO = "estado"


def main():
    parser = argparse.ArgumentParser(description="Batch RAG DepaFix (Mente 360)")
    parser.add_argument(
        "--input",
        default=str(BASE_DIR / "data" / "prospectos.csv"),
        help="CSV de entrada (columnas: nombre,rubro[,edad])",
    )
    parser.add_argument(
        "--output",
        default=str(BASE_DIR / "data" / "prospectos_procesados.csv"),
        help="CSV de salida con el speech generado",
    )
    parser.add_argument(
        "--limite",
        type=int,
        default=5,
        help="Máximo de prospectos a procesar (para cuidar el presupuesto)",
    )
    args = parser.parse_args()

    if not os.path.exists(args.input):
        raise SystemExit(
            f"❌ ERROR: No existe {args.input}. Crea un CSV con columnas: nombre,rubro"
        )

    print("Iniciando motor RAG (Mente 360)...")
    cerebros = cargar_cerebros()

    procesados = []
    with open(args.input, encoding="utf-8", newline="") as f:
        filas = list(csv.DictReader(f))[: max(args.limite, 0)]

    for i, row in enumerate(filas):
        nombre = (row.get("nombre") or "").strip() or "Sin nombre"
        rubro = (row.get("rubro") or "").strip() or "Desconocido"

        print(f"\n[{i + 1}/{len(filas)}] Procesando a: {nombre} ({rubro})...")

        prompt = (
            f"Actúa como el Coach de Ventas (AIRE). Redacta un speech de WhatsApp "
            f"de máximo 3 párrafos para {nombre}, que trabaja en el rubro {rubro}. "
            f"Sé directo y ofrece automatización con IA."
        )

        try:
            row[COLUMNA_SPEECH] = consultar_mente_360(prompt, cerebros)
            row[COLUMNA_ESTADO] = "generado_por_rag"
            print(f"✅ {nombre} procesado.")
        except Exception as error:
            row[COLUMNA_SPEECH] = ""
            row[COLUMNA_ESTADO] = f"error: {error}"
            print(f"❌ {nombre} falló: {error}")

        procesados.append(row)

    if not procesados:
        raise SystemExit("⚠️ No hay filas para procesar; revisa el CSV de entrada.")

    fieldnames = list(procesados[0].keys())
    with open(args.output, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(procesados)

    print(f"\n🏁 BATCH TERMINADO. Revisa {args.output}")


if __name__ == "__main__":
    main()
