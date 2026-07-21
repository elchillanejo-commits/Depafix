"""
Carga clientes desde un CSV (columnas: nombre, rut, rubro, estado) hacia Supabase.
Hace upsert por 'rut': si el rut ya existe en `clientes`, actualiza nombre/rubro/estado;
si no existe, lo inserta.

Uso:
    python cargar_clientes_desde_csv.py clientes.csv
"""
import csv
import os
import sys

import psycopg2
from dotenv import load_dotenv

REQUIRED_COLUMNS = {"nombre", "rut", "rubro", "estado"}


def leer_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        columnas = set(reader.fieldnames or [])
        faltantes = REQUIRED_COLUMNS - columnas
        if faltantes:
            raise ValueError(f"Faltan columnas en el CSV: {faltantes}")
        return [
            {
                "nombre": row["nombre"].strip(),
                "rut": row["rut"].strip(),
                "rubro": row["rubro"].strip(),
                "estado": row["estado"].strip(),
            }
            for row in reader
        ]


def upsert_clientes(clientes):
    load_dotenv()
    dsn = os.environ.get("SUPABASE_DB_URL")
    if not dsn:
        sys.exit("Falta SUPABASE_DB_URL en el archivo .env")

    with psycopg2.connect(dsn) as conn:
        with conn.cursor() as cur:
            for cliente in clientes:
                cur.execute(
                    """
                    insert into clientes (nombre, rut, rubro, estado)
                    values (%(nombre)s, %(rut)s, %(rubro)s, %(estado)s)
                    on conflict (rut) where rut is not null do update
                    set nombre = excluded.nombre,
                        rubro = excluded.rubro,
                        estado = excluded.estado
                    """,
                    cliente,
                )
        conn.commit()


def main():
    if len(sys.argv) != 2:
        sys.exit("Uso: python cargar_clientes_desde_csv.py <archivo.csv>")

    clientes = leer_csv(sys.argv[1])
    print(f"Leidos {len(clientes)} clientes del CSV.")
    upsert_clientes(clientes)
    print(f"Upsert completado: {len(clientes)} filas procesadas en Supabase (tabla clientes).")


if __name__ == "__main__":
    main()
