#!/usr/bin/env python3
"""Carga DS49 vía psycopg2 directo (bypass PostgREST/schema cache)."""
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import psycopg2
from scripts.cargar_decreto_49 import (
    resolver_pdf, extraer_texto, extraer_cabecera, extraer_articulos,
    extraer_materiales, FECHA_PUBLICACION, PDF_FALLBACK_URL, logger,
)

# Sacar de Supabase: Settings -> Database -> Connection string (URI)
DB_HOST = os.environ["SUPABASE_DB_HOST"]  # ej: aws-0-us-east-1.pooler.supabase.com
DB_PASSWORD = os.environ["SUPABASE_DB_PASSWORD"]
DB_USER = os.environ.get("SUPABASE_DB_USER", "postgres.gylyzcjkswltwpouktbi")


def main():
    conn = psycopg2.connect(
        host=DB_HOST, port=5432, dbname="postgres", user=DB_USER, password=DB_PASSWORD,
    )
    conn.autocommit = True
    cur = conn.cursor()

    pdf_path = resolver_pdf()
    texto = extraer_texto(pdf_path)
    numero, titulo = extraer_cabecera(texto)
    articulos = extraer_articulos(texto)
    logger.info(f"Decreto N°{numero} - {len(articulos)} artículos detectados")

    cur.execute(
        """INSERT INTO decretos (numero, titulo, fecha_publicacion, url)
           VALUES (%s, %s, %s, %s)
           ON CONFLICT (numero) DO UPDATE SET titulo=EXCLUDED.titulo
           RETURNING id""",
        (numero, titulo, FECHA_PUBLICACION, PDF_FALLBACK_URL),
    )
    decreto_id = cur.fetchone()[0]

    n_art, n_mat = 0, 0
    for art in articulos:
        cur.execute(
            """INSERT INTO decreto_articulos (decreto_id, numero, contenido)
               VALUES (%s, %s, %s)
               ON CONFLICT (decreto_id, numero) DO UPDATE SET contenido=EXCLUDED.contenido
               RETURNING id""",
            (decreto_id, art["numero"], art["contenido"][:5000]),
        )
        articulo_id = cur.fetchone()[0]
        n_art += 1

        for mat in extraer_materiales(art["contenido"]):
            cur.execute(
                "SELECT id FROM decreto_materiales WHERE articulo_id=%s AND nombre_material=%s",
                (articulo_id, mat),
            )
            if cur.fetchone():
                continue
            cur.execute(
                """INSERT INTO decreto_materiales (articulo_id, nombre_material, codigo_unidad)
                   VALUES (%s, %s, NULL)""",
                (articulo_id, mat),
            )
            n_mat += 1

    logger.info(f"✅ Decreto: 1 | Artículos: {n_art} | Materiales: {n_mat}")
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
