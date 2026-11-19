from __future__ import annotations

import math
import re
import unicodedata
from typing import Any

import pandas as pd

from .config import (
    BLOCK_BY_STREET,
    COMUNA_OBJETIVO,
    ESTADO_ORDEN,
    ESTADOS,
    PLAN_ORDER,
    STREET_DISPLAY,
)


def strip_accents(value: str) -> str:
    return (
        unicodedata.normalize("NFKD", value)
        .encode("ascii", "ignore")
        .decode("ascii")
    )


def clean_spaces(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def normalize_state(value: Any) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "Otro"
    key = clean_spaces(strip_accents(str(value)).casefold())
    return ESTADOS.get(key, "Otro")


def normalize_id(value: Any) -> str:
    text = str(value).strip()
    if text.endswith(".0") and text[:-2].isdigit():
        return text[:-2]
    return text


def canonical_street(raw_street: str) -> str:
    text = strip_accents(raw_street).upper()
    text = re.sub(r"[.,]", " ", text)
    text = re.sub(r"\bAVENIDA\b", "AV", text)
    text = re.sub(r"\bAV\.?\b", " ", text)
    text = clean_spaces(text)
    text = text.replace("BLANCO ENCALDA", "BLANCO ENCALADA")
    text = text.replace("EJERCITO LIBERTADOR", "EJERCITO")
    text = text.replace("AV EJERCITO", "EJERCITO")
    text = text.replace("AV ESPANA", "ESPANA")
    text = re.sub(r"^AV\s+", "", text)
    text = clean_spaces(text).strip(" -")
    return text or "SIN CALLE"


def _extract_torre(upper: str) -> str | None:
    match = re.search(r"\bTORRE\s+([A-Z0-9]+)\b", upper)
    return match.group(1) if match else None


def _extract_departamento(upper: str) -> str | None:
    match = re.search(
        r"\b(?:DEPTO|DEPARTAMENTO|DPTO|DEPT)\.?\s*([A-Z0-9]+(?:-[A-Z0-9]+)?)",
        upper,
    )
    if not match:
        return None
    dept = match.group(1).replace(" ", "")
    trailing = re.search(r",\s*([A-Z0-9])\s*$", upper)
    if trailing and "-" not in dept:
        dept = f"{dept}-{trailing.group(1)}"
    return dept


def _extract_numero(working: str) -> str | None:
    match = re.search(r"\b(\d{1,5})\b", working)
    return match.group(1) if match else None


def _display_street(calle: str, numero: str | None) -> str:
    if calle == "EJERCITO" and numero == "650":
        return "Avenida Ejército Libertador"
    return STREET_DISPLAY.get(calle, calle.title())


def parse_direccion(raw: Any) -> dict[str, Any]:
    original = "" if raw is None or (isinstance(raw, float) and math.isnan(raw)) else clean_spaces(str(raw))
    upper = strip_accents(original).upper()

    if "ADMINISTRACION" in upper:
        return {
            "direccion_original": original,
            "direccion_normalizada": "Administración de departamentos Santiago Centro",
            "calle": "",
            "numero": None,
            "departamento": None,
            "torre": None,
            "es_administracion": True,
            "sin_numero": True,
        }

    torre = _extract_torre(upper)
    departamento = _extract_departamento(upper)

    working = upper
    dept_match = re.search(
        r"\b(?:DEPTO|DEPARTAMENTO|DPTO|DEPT)\.?\s*[A-Z0-9]+(?:-[A-Z0-9]+)?",
        working,
    )
    if dept_match:
        working = working.replace(dept_match.group(0), " ")
    if torre:
        working = re.sub(r"\bTORRE\s+[A-Z0-9]+\b", " ", working)
    if departamento and "-" in departamento:
        working = re.sub(r",\s*[A-Z0-9]\s*$", " ", working)
    working = clean_spaces(working)

    numero = _extract_numero(working)
    if numero:
        street_raw = working[: working.find(numero)]
    else:
        street_raw = working
    street_raw = clean_spaces(street_raw).strip(" ,.-")
    calle = canonical_street(street_raw)
    display = _display_street(calle, numero)

    if numero:
        direccion = f"{display} {numero}"
    else:
        direccion = f"{display} (sin número)"
    if departamento:
        direccion += f", Depto. {departamento}"
    if torre:
        direccion += f", Torre {torre}"

    return {
        "direccion_original": original,
        "direccion_normalizada": direccion,
        "calle": calle,
        "numero": numero,
        "departamento": departamento,
        "torre": torre,
        "es_administracion": False,
        "sin_numero": numero is None,
    }


def _to_number(value: Any) -> float:
    if value is None:
        return math.nan
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if isinstance(value, float) and math.isnan(value):
            return math.nan
        return float(value)
    text = clean_spaces(str(value))
    if text in {"", "-", "nan", "None", "N/A"}:
        return math.nan
    text = text.replace(".", "").replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return math.nan


def _score_ready_to_rent(row: pd.Series) -> int:
    if row["estado"] != "Vacante" or row["es_administracion"]:
        return 0
    score = 40
    superficie = row["superficie_util_m2"]
    if pd.isna(superficie):
        score += 20
    elif superficie <= 45:
        score += 15
    else:
        score += 5
    edad = row["antiguedad_estimada_anios"]
    if pd.notna(edad):
        if edad >= 20:
            score += 15
        elif edad >= 10:
            score += 10
    if row["bloque"] == "Bloque 1":
        score += 10
    dormitorios = row["dormitorios"]
    if pd.notna(dormitorios) and dormitorios <= 1:
        score += 10
    if row["sin_valor"]:
        score += 5
    return min(score, 100)


def _priority(score: int) -> str:
    if score >= 80:
        return "A"
    if score >= 60:
        return "B"
    return "C"


def _ready_action(row: pd.Series) -> str:
    if row["estado"] != "Vacante" or row["es_administracion"]:
        return ""
    if pd.isna(row["superficie_util_m2"]):
        return "Medir superficie; cotizar piso SPC por m² + iluminación LED + enchufes + soporte TV."
    if row["superficie_util_m2"] <= 45:
        return "Quick win: piso SPC, plafones LED, enchufes y soporte TV; validar agua caliente."
    return "Remodelación estándar: piso SPC, iluminación, enchufes y soporte TV; presupuestar por partidas."


def _suggested_quantities(row: pd.Series) -> tuple[float, bool, int, int, int]:
    if row["es_administracion"]:
        return 0.0, False, 0, 0, 0
    superficie = row["superficie_util_m2"]
    m2 = float(superficie) if pd.notna(superficie) else 35.0
    m2_estimado = pd.isna(superficie)
    dormitorios = row["dormitorios"]
    banos = row["banos"]
    if pd.notna(dormitorios) and pd.notna(banos):
        plafones = max(3, int(dormitorios) + int(banos) + 2)
    else:
        plafones = 6
    if pd.notna(dormitorios):
        enchufes = max(4, int(dormitorios) * 2 + 2)
    else:
        enchufes = 6
    return m2, m2_estimado, plafones, enchufes, 1


def _merge_catastro(df: pd.DataFrame, catastro: pd.DataFrame) -> pd.DataFrame:
    if catastro.empty:
        df["anio_desde"] = math.nan
        df["anio_hasta"] = math.nan
        df["antiguedad_confianza"] = "sin dato"
        df["antiguedad_fuente"] = "Sin catastro referencial"
        return df

    left = df.copy()
    left["_numero_match"] = left["numero"].fillna("").astype(str)
    right = catastro.copy()
    right["numero"] = right["numero"].fillna("").astype(str)
    right["calle"] = right["calle"].astype(str).str.upper()
    right = right.rename(
        columns={
            "confianza": "antiguedad_confianza",
            "fuente": "antiguedad_fuente",
        }
    )

    exact = right.drop_duplicates(subset=["calle", "numero"], keep="first")
    merged = left.merge(
        exact,
        how="left",
        left_on=["calle", "_numero_match"],
        right_on=["calle", "numero"],
        suffixes=("", "_catastro"),
    )

    missing = merged["anio_desde"].isna() & ~merged["es_administracion"]
    if missing.any():
        street_only = right[right["numero"] == ""].drop_duplicates(subset=["calle"], keep="first")
        street_only = street_only.rename(
            columns={
                "anio_desde": "anio_desde_fallback",
                "anio_hasta": "anio_hasta_fallback",
                "antiguedad_confianza": "confianza_fallback",
                "antiguedad_fuente": "fuente_fallback",
            }
        )
        fallback = merged.loc[missing, ["calle"]].merge(
            street_only[["calle", "anio_desde_fallback", "anio_hasta_fallback", "confianza_fallback", "fuente_fallback"]],
            how="left",
            on="calle",
        )
        merged.loc[missing, "anio_desde"] = fallback["anio_desde_fallback"].to_numpy()
        merged.loc[missing, "anio_hasta"] = fallback["anio_hasta_fallback"].to_numpy()
        merged.loc[missing, "antiguedad_confianza"] = fallback["confianza_fallback"].to_numpy()
        merged.loc[missing, "antiguedad_fuente"] = fallback["fuente_fallback"].to_numpy()

    merged["antiguedad_confianza"] = merged["antiguedad_confianza"].fillna("sin dato")
    merged["antiguedad_fuente"] = merged["antiguedad_fuente"].fillna("Sin catastro referencial")
    return merged


def build_dataset(raw: pd.DataFrame, catastro: pd.DataFrame, anio_actual: int = 2026) -> pd.DataFrame:
    required = {"Id", "Dirección", "Comuna", "Estado Propiedad"}
    missing_columns = required - set(raw.columns)
    if missing_columns:
        raise ValueError(f"Faltan columnas obligatorias en el xlsx: {sorted(missing_columns)}")

    filtered = raw[
        raw["Comuna"].astype(str).str.strip().str.casefold() == COMUNA_OBJETIVO.casefold()
    ].copy()
    if filtered.empty:
        raise ValueError("No hay propiedades en la comuna de Santiago.")

    parsed = pd.DataFrame([parse_direccion(value) for value in filtered["Dirección"]])
    filtered = filtered.reset_index(drop=True)
    parsed = parsed.reset_index(drop=True).drop(columns=["direccion_original"])

    df = pd.DataFrame(
        {
            "id": filtered["Id"].map(normalize_id),
            "direccion_original": filtered["Dirección"].astype(str),
            "comuna": "Santiago",
            "tipo_propiedad": filtered.get("Tipo de propiedad", pd.Series(index=filtered.index, dtype=object)).fillna("Departamento"),
            "estado_original": filtered["Estado Propiedad"],
            "valor_arriendo_clp": filtered.get("Valor de arriendo", pd.Series(index=filtered.index, dtype=object)).map(_to_number),
            "superficie_util_m2": filtered.get("Superficie útil", pd.Series(index=filtered.index, dtype=object)).map(_to_number),
            "dormitorios": filtered.get("# dormitorios", pd.Series(index=filtered.index, dtype=object)).map(_to_number),
            "banos": filtered.get("# baños", pd.Series(index=filtered.index, dtype=object)).map(_to_number),
            "estacionamientos": filtered.get("# estacionamientos", pd.Series(index=filtered.index, dtype=object)).map(_to_number),
            "bodegas": filtered.get("# bodegas", pd.Series(index=filtered.index, dtype=object)).map(_to_number),
        }
    )
    df = pd.concat([df, parsed], axis=1)
    df["estado"] = df["estado_original"].map(normalize_state)
    df["es_vacante"] = df["estado"] == "Vacante"
    df["es_administracion"] = df["es_administracion"].astype(bool)
    df["sin_numero"] = df["sin_numero"].astype(bool)
    df["sin_superficie"] = df["superficie_util_m2"].isna()
    df["sin_dormitorios"] = df["dormitorios"].isna()
    df["sin_banos"] = df["banos"].isna()
    df["sin_valor"] = df["valor_arriendo_clp"].isna() | (df["valor_arriendo_clp"] == 0)
    df["bloque"] = df.apply(
        lambda row: "Administración" if row["es_administracion"] else BLOCK_BY_STREET.get(row["calle"], "Sin asignar"),
        axis=1,
    )
    df["orden_plan"] = df.apply(
        lambda row: PLAN_ORDER.get((row["calle"], row["numero"] or ""), 999),
        axis=1,
    )

    group_sizes = df.groupby("direccion_normalizada")["id"].transform("size")
    df["unidades_en_direccion"] = group_sizes.astype(int)
    df["duplicado_direccion"] = df["unidades_en_direccion"] > 1

    df = _merge_catastro(df, catastro)
    df["anio_estimado"] = ((df["anio_desde"] + df["anio_hasta"]) / 2).round(0)
    df["antiguedad_estimada_anios"] = (anio_actual - df["anio_estimado"]).round(0)
    df["antiguedad_rango"] = df.apply(
        lambda row: (
            f"{int(anio_actual - row['anio_hasta'])}-{int(anio_actual - row['anio_desde'])} años"
            if pd.notna(row["anio_desde"]) and pd.notna(row["anio_hasta"])
            else "sin dato"
        ),
        axis=1,
    )
    df["antiguedad_estimada_anios"] = df["antiguedad_estimada_anios"].astype("Float64")

    df["score_ready_to_rent"] = df.apply(_score_ready_to_rent, axis=1).astype(int)
    df["prioridad_ready_to_rent"] = df["score_ready_to_rent"].map(
        lambda score: _priority(score) if score > 0 else "No aplica"
    )
    df["accion_ready_to_rent"] = df.apply(_ready_action, axis=1)
    quantities = df.apply(_suggested_quantities, axis=1)
    df["m2_piso_spc_sugerido"] = [item[0] for item in quantities]
    df["m2_piso_spc_estimado"] = [item[1] for item in quantities]
    df["plafones_led_sugeridos"] = [item[2] for item in quantities]
    df["enchufes_sugeridos"] = [item[3] for item in quantities]
    df["soporte_tv_sugerido"] = [item[4] for item in quantities]
    df["uplift_estimado_clp"] = df["estado"].map(
        lambda estado: "50.000 - 80.000 CLP/mes" if estado == "Vacante" else ""
    )

    observaciones: list[str] = []
    for _, row in df.iterrows():
        notas: list[str] = []
        if row["es_administracion"]:
            notas.append("Registro administrativo; no visitar.")
        if row["sin_numero"] and not row["es_administracion"]:
            notas.append("Sin número: confirmar dirección con corredor.")
        if row["duplicado_direccion"]:
            notas.append(f"Dirección repetida ({row['unidades_en_direccion']} registros): confirmar si son unidades distintas.")
        faltantes = [
            nombre
            for nombre, flag in (
                ("superficie", row["sin_superficie"]),
                ("dormitorios", row["sin_dormitorios"]),
                ("baños", row["sin_banos"]),
                ("valor de arriendo", row["sin_valor"]),
            )
            if flag
        ]
        if faltantes:
            notas.append("Sin dato en origen: " + ", ".join(faltantes) + ".")
        if row["estado"] == "Otro":
            notas.append(f"Estado no reconocido: {row['estado_original']!r}.")
        if pd.isna(row["antiguedad_estimada_anios"]) and not row["es_administracion"]:
            notas.append("Sin referencia de antigüedad.")
        observaciones.append(" ".join(notas))
    df["observaciones"] = observaciones
    df["requiere_revision"] = (
        df["es_administracion"]
        | df["sin_numero"]
        | df["duplicado_direccion"]
        | (df["estado"] == "Otro")
        | df["sin_superficie"]
        | df["sin_dormitorios"]
        | df["sin_banos"]
        | df["sin_valor"]
        | df["antiguedad_estimada_anios"].isna()
    )
    df["estado_orden"] = df["estado"].map(ESTADO_ORDEN).fillna(9)
    df["bloque_orden"] = df["bloque"].map(
        {"Bloque 1": 1, "Bloque 2": 2, "Bloque 3": 3, "Administración": 8, "Sin asignar": 9}
    ).fillna(9)
    df = df.sort_values(
        ["bloque_orden", "orden_plan", "departamento", "id"],
        na_position="last",
    ).reset_index(drop=True)

    vacantes = df[(df["es_vacante"]) & (~df["es_administracion"])].copy()
    vacantes = vacantes.sort_values(
        ["score_ready_to_rent", "antiguedad_estimada_anios", "id"],
        ascending=[False, False, True],
    )
    df["rank_ready_to_rent"] = pd.NA
    for rank, index in enumerate(vacantes.index, start=1):
        df.loc[index, "rank_ready_to_rent"] = rank
    df["rank_ready_to_rent"] = df["rank_ready_to_rent"].astype("Int64")

    return df
