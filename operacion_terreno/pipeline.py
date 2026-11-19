from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pandas as pd

from .catastro import load_catastro
from .config import (
    DATOS_DIR,
    DEFAULT_CATASTRO,
    DEFAULT_DB_PATH,
    DEFAULT_DDL,
    DEFAULT_GEOCODE_CACHE,
    DEFAULT_NORMALIZED_CSV,
    DEFAULT_OUTDIR,
    DEFAULT_PLAN,
    DEFAULT_ROUTES_JSON,
    DEFAULT_XLSX,
    HOJA_PROPIEDADES,
    SQL_DIR,
)
from .db import generate_postgres_ddl, init_db, seed_pending_inspections
from .exportacion import (
    write_checklist,
    write_excel,
    write_normalized_csv,
    write_routes_json,
)
from .geocoding import geocode_dataframe
from .normalizacion import build_dataset
from .rutas import build_routes

logger = logging.getLogger(__name__)


def _catastro_coverage(df: pd.DataFrame) -> str:
    total = len(df)
    if not total:
        return "0/0 (0%)"
    covered = int(df["antiguedad_estimada_anios"].notna().sum())
    return f"{covered}/{total} ({covered / total:.0%})"


def run_pipeline(
    xlsx_path: Path = DEFAULT_XLSX,
    plan_path: Path = DEFAULT_PLAN,
    outdir: Path = DEFAULT_OUTDIR,
    catastro_path: Path = DEFAULT_CATASTRO,
    geocode_cache: Path = DEFAULT_GEOCODE_CACHE,
    db_path: Path = DEFAULT_DB_PATH,
    ddl_path: Path = DEFAULT_DDL,
    normalized_csv: Path = DEFAULT_NORMALIZED_CSV,
    routes_json: Path = DEFAULT_ROUTES_JSON,
    enable_geocoding: bool = True,
    max_geocode: int | None = None,
    anio_actual: int = 2026,
) -> dict[str, Any]:
    if not xlsx_path.exists():
        raise FileNotFoundError(f"No existe el xlsx: {xlsx_path}")
    if not plan_path.exists():
        logger.warning("No existe el plan de ruta: %s", plan_path)

    logger.info("Leyendo %s", xlsx_path)
    raw = pd.read_excel(xlsx_path, sheet_name=HOJA_PROPIEDADES, dtype={"Id": str})
    logger.info("Filas origen: %s", len(raw))

    catastro = load_catastro(catastro_path)
    logger.info("Catastro referencial: %s filas", len(catastro))

    df = build_dataset(raw, catastro, anio_actual=anio_actual)
    logger.info("Propiedades Santiago: %s", len(df))

    df, geo_meta = geocode_dataframe(
        df,
        cache_path=geocode_cache,
        enabled=enable_geocoding,
        max_queries=max_geocode,
    )
    routes_df, df, route_meta = build_routes(df)

    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    DATOS_DIR.mkdir(parents=True, exist_ok=True)
    SQL_DIR.mkdir(parents=True, exist_ok=True)

    normalized_csv = write_normalized_csv(df, Path(normalized_csv))
    routes_json = write_routes_json(routes_df, Path(routes_json))

    meta: dict[str, Any] = {
        **route_meta,
        "catastro_cobertura": _catastro_coverage(df),
        "catastro_path": str(catastro_path),
        "plan_path": str(plan_path),
        "xlsx_path": str(xlsx_path),
        "geocoding": geo_meta,
    }

    excel_path = outdir / "RUTA_TERRENO_STGO_CENTRO.xlsx"
    checklist_path = outdir / "CHECKLIST_MOVIL.md"
    write_excel(df, routes_df, catastro, meta, excel_path)
    write_checklist(df, routes_df, meta, checklist_path)

    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    engine = init_db(f"sqlite:///{db_path}")
    seed_stats = seed_pending_inspections(engine, df)
    ddl_path = generate_postgres_ddl(Path(ddl_path))

    meta.update(
        {
            "excel_path": str(excel_path),
            "checklist_path": str(checklist_path),
            "db_path": str(db_path),
            "ddl_path": str(ddl_path),
            "normalized_csv": str(normalized_csv),
            "routes_json": str(routes_json),
            "seed": seed_stats,
        }
    )

    logger.info("Excel: %s", excel_path)
    logger.info("Checklist: %s", checklist_path)
    logger.info("DB: %s", db_path)
    logger.info("DDL: %s", ddl_path)
    logger.info(
        "Paradas: %s | Segmentos: %s | Geocodificadas: %s | Vacantes: %s",
        meta.get("paradas"),
        meta.get("segmentos"),
        meta.get("geocodificadas"),
        int(((df["es_vacante"]) & (~df["es_administracion"])).sum()),
    )
    return meta
