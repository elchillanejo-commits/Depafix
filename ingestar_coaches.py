#!/usr/bin/env python3
"""Ingesta el conocimiento de los coaches en Supabase."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
from supabase import Client, create_client

BASE_DIR = Path(__file__).resolve().parent
ARCHIVO_ENV = BASE_DIR / ".env"
CONOCIMIENTO = Path("/home/ibar/Documentos/Conocimiento")

MODELO = "intfloat/multilingual-e5-small"
DIMENSIONES = 384
TAMANO_FRAGMENTO = 1000
SOLAPE = 200
MINIMO_FRAGMENTO = 100
LOTE_EMBEDDINGS = 32
LOTE_INSERCION = 25

EXTENSIONES = {".txt", ".md", ".pdf", ".csv", ".xlsx", ".xls", ".json"}

FUENTES: tuple[dict[str, Any], ...] = (
    {
        "clave": "aire",
        "nombre": "Aire / Marketing",
        "tabla": "coach_pitches",
        "elemento": "aire",
        "carpetas": (
            CONOCIMIENTO / "Aire_Marketing",
            CONOCIMIENTO / "Ventas",
        ),
    },
    {
        "clave": "fuego",
        "nombre": "Fuego / IA",
        "tabla": "coach_python",
        "elemento": "fuego",
        "carpetas": (
            CONOCIMIENTO / "Fuego_IA",
            CONOCIMIENTO / "IA",
        ),
    },
    {
        "clave": "agua",
        "nombre": "Agua / Dropshipping",
        "tabla": "coach_shopify",
        "elemento": "agua",
        "carpetas": (
            CONOCIMIENTO / "Agua_Dropshipping",
            CONOCIMIENTO / "Dropshiphing",
        ),
    },
)


def cargar_env() -> None:
    load_dotenv(ARCHIVO_ENV, override=True)


def crear_cliente() -> Client:
    url = os.getenv("SUPABASE_URL", "").strip()
    key = (
        os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
        or os.getenv("SUPABASE_KEY", "").strip()
    )
    if not url or not key:
        raise SystemExit(
            "Faltan SUPABASE_URL y SUPABASE_SERVICE_ROLE_KEY (o SUPABASE_KEY) en .env"
        )
    return create_client(url, key)


def archivos_de(carpeta: Path) -> list[Path]:
    if not carpeta.is_dir():
        return []
    return sorted(
        ruta
        for ruta in carpeta.rglob("*")
        if ruta.is_file() and ruta.suffix.lower() in EXTENSIONES
    )


def leer_archivo(ruta: Path) -> str:
    sufijo = ruta.suffix.lower()
    if sufijo in {".txt", ".md", ".json"}:
        return ruta.read_text(encoding="utf-8", errors="replace")
    if sufijo == ".pdf":
        try:
            import pdfplumber
        except ImportError as error:
            raise RuntimeError("falta pdfplumber para leer PDFs") from error
        with pdfplumber.open(ruta) as pdf:
            return "\n".join((pagina.extract_text() or "") for pagina in pdf.pages)
    if sufijo == ".csv":
        try:
            import pandas as pd
        except ImportError as error:
            raise RuntimeError("falta pandas para leer CSV") from error
        return pd.read_csv(ruta).to_csv(index=False)
    if sufijo in {".xlsx", ".xls"}:
        try:
            import pandas as pd
        except ImportError as error:
            raise RuntimeError("falta pandas para leer Excel") from error
        try:
            hojas = pd.read_excel(ruta, sheet_name=None)
        except ImportError as error:
            raise RuntimeError("falta openpyxl para leer Excel") from error
        return "\n\n".join(hoja.to_csv(index=False) for hoja in hojas.values())
    return ""


def dividir(texto: str) -> list[str]:
    texto = texto.strip()
    if not texto:
        return []

    fragmentos: list[str] = []
    inicio = 0
    while inicio < len(texto):
        fin = min(inicio + TAMANO_FRAGMENTO, len(texto))
        if fin < len(texto):
            corte = texto.rfind("\n", inicio + TAMANO_FRAGMENTO // 2, fin)
            if corte == -1:
                corte = texto.rfind(" ", inicio + TAMANO_FRAGMENTO // 2, fin)
            if corte != -1:
                fin = corte

        fragmento = texto[inicio:fin].strip()
        if len(fragmento) >= MINIMO_FRAGMENTO:
            fragmentos.append(fragmento)

        if fin >= len(texto):
            break
        inicio = max(fin - SOLAPE, inicio + 1)

    return fragmentos


def verificar_tabla(sb: Client, tabla: str) -> None:
    try:
        sb.table(tabla).select("id").limit(1).execute()
    except Exception as error:
        mensaje = str(error)
        if "PGRST205" in mensaje or "Could not find the table" in mensaje:
            raise SystemExit(
                f"La tabla {tabla} no existe. Ejecuta sql/coach_tables.sql en Supabase."
            ) from error
        raise


def ingestar_fuente(
    fuente: dict[str, Any],
    modelo: SentenceTransformer | None,
    sb: Client | None,
    dry_run: bool,
    limpiar: bool,
) -> tuple[int, int, int]:
    tabla = fuente["tabla"]
    print(f"\n[{fuente['nombre']}] tabla={tabla}")

    carpetas = [carpeta for carpeta in fuente["carpetas"] if carpeta.is_dir()]
    if not carpetas:
        print("  Sin carpetas de origen; se omite.")
        return 0, 0, 0

    archivos: list[Path] = []
    for carpeta in carpetas:
        encontrados = archivos_de(carpeta)
        print(f"  Carpeta: {carpeta} ({len(encontrados)} archivos)")
        archivos.extend(encontrados)

    if not archivos:
        print("  No se encontraron archivos compatibles.")
        return 0, 0, 0

    if not dry_run:
        assert sb is not None
        verificar_tabla(sb, tabla)
        if limpiar:
            sb.table(tabla).delete().gte("id", 0).execute()
            print("  Tabla limpiada antes de la ingesta.")

    archivos_ok = 0
    archivos_error = 0
    total_fragmentos = 0

    for ruta in archivos:
        print(f"  Procesando: {ruta.name}")
        try:
            fragmentos = dividir(leer_archivo(ruta))
            if not fragmentos:
                print("    Omitido: sin texto útil.")
                continue

            print(f"    Fragmentos: {len(fragmentos)}")
            if dry_run:
                archivos_ok += 1
                total_fragmentos += len(fragmentos)
                continue

            assert sb is not None and modelo is not None
            for inicio in range(0, len(fragmentos), LOTE_INSERCION):
                lote = fragmentos[inicio : inicio + LOTE_INSERCION]
                vectores = modelo.encode(
                    [f"passage: {fragmento}" for fragmento in lote],
                    batch_size=LOTE_EMBEDDINGS,
                    normalize_embeddings=True,
                    show_progress_bar=False,
                )
                filas = [
                    {
                        "contenido": fragmento,
                        "metadata": {
                            "elemento": fuente["elemento"],
                            "coach": fuente["clave"],
                            "fuente": ruta.name,
                            "ruta": str(ruta),
                        },
                        "embedding": vector.tolist(),
                    }
                    for fragmento, vector in zip(lote, vectores)
                ]
                sb.table(tabla).insert(filas).execute()
                total_fragmentos += len(filas)

            archivos_ok += 1
        except Exception as error:
            archivos_error += 1
            print(f"    ERROR: {type(error).__name__}: {str(error)[:200]}")

    return archivos_ok, archivos_error, total_fragmentos


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Ingesta conocimiento de coaches en Supabase."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Muestra qué se subiría sin insertar nada.",
    )
    parser.add_argument(
        "--solo",
        choices=[fuente["clave"] for fuente in FUENTES],
        help="Procesa solo una fuente.",
    )
    parser.add_argument(
        "--limpiar",
        action="store_true",
        help="Borra la tabla destino antes de insertar.",
    )
    parser.add_argument(
        "--modelo",
        default=MODELO,
        help=f"Modelo de embeddings (por defecto: {MODELO}).",
    )
    args = parser.parse_args()

    cargar_env()

    fuentes = [
        fuente
        for fuente in FUENTES
        if args.solo is None or fuente["clave"] == args.solo
    ]

    sb = None if args.dry_run else crear_cliente()
    modelo = None if args.dry_run else SentenceTransformer(args.modelo)
    if modelo is not None:
        if hasattr(modelo, "get_embedding_dimension"):
            dimension = modelo.get_embedding_dimension()
        else:
            dimension = modelo.get_sentence_embedding_dimension()
        if dimension != DIMENSIONES:
            raise SystemExit(
                f"El modelo {args.modelo} genera vectores de {dimension} dimensiones; "
                f"las tablas esperan {DIMENSIONES}."
            )

    total_ok = 0
    total_error = 0
    total_fragmentos = 0

    for fuente in fuentes:
        ok, error, fragmentos = ingestar_fuente(
            fuente, modelo, sb, args.dry_run, args.limpiar
        )
        total_ok += ok
        total_error += error
        total_fragmentos += fragmentos

    print(
        f"\nResumen: {total_ok} archivos OK, {total_error} con error, "
        f"{total_fragmentos} fragmentos."
    )
    if args.dry_run:
        print("DRY-RUN: no se insertó nada en Supabase.")

    if total_ok == 0:
        print("No se ingestó ningún archivo.")
        return 1
    return 1 if total_error else 0


if __name__ == "__main__":
    raise SystemExit(main())
