#!/usr/bin/env python3
"""Fusiona todos los .txt de una carpeta en un único conocimiento_[tema].txt."""

from __future__ import annotations

import argparse
import fnmatch
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
SALIDA_DEFECTO = BASE_DIR / "data" / "fusionados"
SEPARADOR = "\n\n" + "=" * 80 + "\n"


def normalizar_tema(tema: str) -> str:
    limpio = re.sub(r"[^a-zA-Z0-9_-]+", "_", tema.strip().lower())
    return limpio.strip("_") or "general"


def buscar_txt(carpeta: Path, patron: str, recursivo: bool) -> list[Path]:
    if not carpeta.is_dir():
        raise SystemExit(f"No existe la carpeta: {carpeta}")
    candidatos = carpeta.rglob("*") if recursivo else carpeta.glob("*")
    patron = patron.lower()
    return sorted(
        ruta
        for ruta in candidatos
        if ruta.is_file()
        and ruta.suffix.lower() == ".txt"
        and fnmatch.fnmatch(ruta.name.lower(), patron)
    )


def fusionar(
    carpeta: Path,
    tema: str,
    salida: Path,
    patron: str,
    recursivo: bool,
    encabezados: bool,
) -> tuple[Path, int, int]:
    destino = (salida / f"conocimiento_{normalizar_tema(tema)}.txt").resolve()
    archivos = [
        ruta
        for ruta in buscar_txt(carpeta.expanduser(), patron, recursivo)
        if ruta.resolve() != destino
    ]
    if not archivos:
        raise SystemExit(
            f"No hay archivos .txt que coincidan con '{patron}' en {carpeta}"
        )

    salida = salida.expanduser()
    salida.mkdir(parents=True, exist_ok=True)
    total_archivos = 0
    total_caracteres = 0

    with destino.open("w", encoding="utf-8") as archivo_salida:
        for ruta in archivos:
            texto = ruta.read_text(encoding="utf-8-sig", errors="replace").strip()
            if not texto:
                continue
            if encabezados:
                archivo_salida.write(f"{SEPARADOR}FUENTE: {ruta.name}\n{SEPARADOR}\n")
            archivo_salida.write(texto)
            archivo_salida.write("\n")
            total_archivos += 1
            total_caracteres += len(texto)

    if total_archivos == 0:
        destino.unlink(missing_ok=True)
        raise SystemExit(f"Todos los .txt de {carpeta} están vacíos.")

    return destino, total_archivos, total_caracteres


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fusiona los .txt de una carpeta en conocimiento_[tema].txt."
    )
    parser.add_argument(
        "--carpeta", required=True, type=Path, help="Carpeta de origen con los .txt."
    )
    parser.add_argument("--tema", required=True, help="Tema del conocimiento a fusionar.")
    parser.add_argument(
        "--salida",
        type=Path,
        default=SALIDA_DEFECTO,
        help=f"Carpeta de destino (por defecto: {SALIDA_DEFECTO}).",
    )
    parser.add_argument(
        "--patron",
        default="*.txt",
        help="Patrón de archivos, sin distinguir mayúsculas (por defecto: *.txt).",
    )
    parser.add_argument(
        "--no-recursivo",
        action="store_true",
        help="No entrar en subcarpetas.",
    )
    parser.add_argument(
        "--sin-encabezados",
        action="store_true",
        help="No agregar el separador con el nombre de cada archivo.",
    )
    args = parser.parse_args()

    destino, archivos, caracteres = fusionar(
        carpeta=args.carpeta,
        tema=args.tema,
        salida=args.salida,
        patron=args.patron,
        recursivo=not args.no_recursivo,
        encabezados=not args.sin_encabezados,
    )
    print(
        f"OK: {archivos} archivos, {caracteres:,} caracteres -> {destino}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
