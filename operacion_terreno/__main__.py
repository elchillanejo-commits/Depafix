from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from .config import (
    DEFAULT_CATASTRO,
    DEFAULT_DB_PATH,
    DEFAULT_DDL,
    DEFAULT_GEOCODE_CACHE,
    DEFAULT_NORMALIZED_CSV,
    DEFAULT_OUTDIR,
    DEFAULT_PLAN,
    DEFAULT_ROUTES_JSON,
    DEFAULT_XLSX,
)
from .pipeline import run_pipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Pipeline de visitas, rutas y presupuestos para Santiago Centro.",
    )
    parser.add_argument("--xlsx", type=Path, default=DEFAULT_XLSX, help="Planilla de propiedades.")
    parser.add_argument("--plan", type=Path, default=DEFAULT_PLAN, help="Plan de ruta y presupuestos.")
    parser.add_argument("--outdir", type=Path, default=DEFAULT_OUTDIR, help="Carpeta de entregables.")
    parser.add_argument("--catastro", type=Path, default=DEFAULT_CATASTRO, help="CSV de catastro referencial.")
    parser.add_argument("--cache", type=Path, default=DEFAULT_GEOCODE_CACHE, help="Caché de geocodificación.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH, help="Ruta SQLite.")
    parser.add_argument("--ddl", type=Path, default=DEFAULT_DDL, help="Ruta DDL PostgreSQL.")
    parser.add_argument("--csv", type=Path, default=DEFAULT_NORMALIZED_CSV, help="CSV normalizado.")
    parser.add_argument("--routes-json", type=Path, default=DEFAULT_ROUTES_JSON, help="JSON de rutas.")
    parser.add_argument("--anio", type=int, default=2026, help="Año de referencia para antigüedad.")
    parser.add_argument("--no-geocode", action="store_true", help="No consultar Nominatim; usar direcciones.")
    parser.add_argument("--max-geocode", type=int, default=None, help="Máximo de consultas nuevas a Nominatim.")
    parser.add_argument("--verbose", action="store_true", help="Log detallado.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )
    try:
        meta = run_pipeline(
            xlsx_path=args.xlsx,
            plan_path=args.plan,
            outdir=args.outdir,
            catastro_path=args.catastro,
            geocode_cache=args.cache,
            db_path=args.db,
            ddl_path=args.ddl,
            normalized_csv=args.csv,
            routes_json=args.routes_json,
            enable_geocoding=not args.no_geocode,
            max_geocode=args.max_geocode,
            anio_actual=args.anio,
        )
    except Exception as exc:
        logging.error("Pipeline falló: %s", exc)
        if args.verbose:
            raise
        return 1

    print("PIPELINE OK")
    print(f"Propiedades Santiago: {meta.get('unidades', 0)} unidades / {meta.get('paradas', 0)} paradas")
    print(f"Segmentos de ruta: {meta.get('segmentos', 0)}")
    print(f"Geocodificadas: {meta.get('geocodificadas', 0)} paradas")
    print(f"Catastro referencial: {meta.get('catastro_cobertura', 's/d')}")
    print(f"Excel: {meta.get('excel_path')}")
    print(f"Checklist: {meta.get('checklist_path')}")
    print(f"DB: {meta.get('db_path')}")
    print(f"DDL: {meta.get('ddl_path')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
