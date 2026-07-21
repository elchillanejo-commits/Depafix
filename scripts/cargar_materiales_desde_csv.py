"""
Carga materiales desde un CSV (columnas: material, cantidad, precio_unitario,
rubro [opcional]) hacia la tabla `line_items` de Supabase.

Por ahora solo inserta filas nuevas (no hace upsert): line_items no tiene una
restricción unique sobre (material, record_id) que permita un ON CONFLICT.

Uso:
    python cargar_materiales_desde_csv.py materiales.csv
"""
import csv
import os
import sys

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

REQUIRED_COLUMNS = {"material", "cantidad", "precio_unitario"}


def leer_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        columnas = set(reader.fieldnames or [])
        faltantes = REQUIRED_COLUMNS - columnas
        if faltantes:
            raise ValueError(f"Faltan columnas en el CSV: {faltantes}")

        filas = []
        for row in reader:
            filas.append(
                (
                    row["material"].strip(),
                    int(row["cantidad"]),
                    float(row["precio_unitario"]),
                    (row.get("rubro") or "").strip() or None,
                )
            )
        return filas


def insertar_materiales(filas):
    load_dotenv()
    dsn = os.environ.get("SUPABASE_DB_URL")
    if not dsn:
        sys.exit("Falta SUPABASE_DB_URL en el archivo .env")

    with psycopg2.connect(dsn) as conn:
        with conn.cursor() as cur:
            psycopg2.extras.execute_values(
                cur,
                """
                insert into line_items (material, cantidad, precio_unitario, rubro)
                values %s
                """,
                filas,
            )
        conn.commit()


def main():
    if len(sys.argv) != 2:
        sys.exit("Uso: python cargar_materiales_desde_csv.py <archivo.csv>")

    filas = leer_csv(sys.argv[1])
    print(f"Leidos {len(filas)} materiales del CSV.")
    insertar_materiales(filas)
    print(f"Insercion completada: {len(filas)} filas nuevas en line_items.")


if __name__ == "__main__":
    main()
