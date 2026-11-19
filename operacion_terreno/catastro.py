from __future__ import annotations

from pathlib import Path

import pandas as pd

from .config import CATASTRO_COLUMNS, CATASTRO_ROWS


def ensure_catastro_csv(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        pd.DataFrame(CATASTRO_ROWS, columns=CATASTRO_COLUMNS).to_csv(path, index=False)
    return path


def load_catastro(path: Path) -> pd.DataFrame:
    ensure_catastro_csv(path)
    df = pd.read_csv(path, dtype={"numero": str})
    expected = set(CATASTRO_COLUMNS)
    missing = expected - set(df.columns)
    if missing:
        raise ValueError(f"Catastro incompleto; faltan columnas: {sorted(missing)}")
    df["calle"] = df["calle"].astype(str).str.upper().str.strip()
    df["numero"] = df["numero"].fillna("").astype(str).str.strip()
    df["anio_desde"] = pd.to_numeric(df["anio_desde"], errors="coerce")
    df["anio_hasta"] = pd.to_numeric(df["anio_hasta"], errors="coerce")
    return df
