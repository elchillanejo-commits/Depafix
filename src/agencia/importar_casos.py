"""
importar_casos.py — Importa casos de éxito a la tabla casos_exito de Supabase.

Fuente única identificada: scripts/insert_caso_real.sql (caso Cordillera,
commit dd00da2). Los PDF de data/expedientes/ y data/raw/ son expedientes
judiciales del Poder Judicial (no casos de marketing) y se excluyen a propósito.

Requiere aplicar antes 07_IKKI_MARKETING/sql/08_casos_exito_extend.sql
(columna slug + índice único, usados para el upsert idempotente).

Uso:
    python -m src.agencia.importar_casos                 # dry-run (por defecto, sin red)
    python -m src.agencia.importar_casos --incluir-estimaciones
    python -m src.agencia.importar_casos --ejecutar      # escribe en Supabase
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FUENTES = [PROJECT_ROOT / "scripts" / "insert_caso_real.sql"]
TABLA = "casos_exito"
POR_CONFIRMAR = None  # Campos sin dato en la fuente: se dejan NULL, no se inventan.


# ------------------------------------------------------------------ parseo SQL
def _parsear_valor(token: str) -> Any:
    token = token.strip()
    if token.upper() == "NULL":
        return None
    if token.startswith("'") and token.endswith("'"):
        return token[1:-1].replace("''", "'")
    if re.fullmatch(r"-?\d+", token):
        return int(token)
    if re.fullmatch(r"-?\d+\.\d+", token):
        return float(token)
    raise ValueError(f"Valor SQL no soportado: {token!r}")


def _dividir_tuplas(bloque: str) -> list[list[str]]:
    """Divide '(a, 'b,c'), (d, e)' en tuplas, respetando comillas simples."""
    tuplas, actual, token = [], None, []
    en_texto = False
    i = 0
    while i < len(bloque):
        c = bloque[i]
        if en_texto:
            token.append(c)
            if c == "'":
                if i + 1 < len(bloque) and bloque[i + 1] == "'":
                    token.append("'")
                    i += 1
                else:
                    en_texto = False
        elif c == "'":
            en_texto = True
            token.append(c)
        elif c == "(" and actual is None:
            actual, token = [], []
        elif c == "," and actual is not None:
            actual.append("".join(token))
            token = []
        elif c == ")" and actual is not None:
            actual.append("".join(token))
            tuplas.append(actual)
            actual, token = None, []
        elif actual is not None:
            token.append(c)
        i += 1
    return tuplas


def leer_inserts(ruta: Path, tabla: str = TABLA) -> list[dict[str, Any]]:
    sql = ruta.read_text(encoding="utf-8")
    sql = re.sub(r"--[^\n]*", "", sql)
    patron = re.compile(
        rf"INSERT\s+INTO\s+(?:public\.)?{tabla}\s*\(([^)]*)\)\s*VALUES\s*(.*?);",
        re.IGNORECASE | re.DOTALL,
    )
    filas = []
    for columnas_txt, valores_txt in patron.findall(sql):
        columnas = [c.strip() for c in columnas_txt.split(",")]
        for tupla in _dividir_tuplas(valores_txt):
            valores = [_parsear_valor(v) for v in tupla]
            if len(valores) != len(columnas):
                raise ValueError(f"{ruta.name}: {len(columnas)} columnas vs {len(valores)} valores")
            filas.append(dict(zip(columnas, valores)))
    return filas


# ------------------------------------------------------------------ normalización
def _slug(*partes: str | None) -> str:
    texto = "-".join(p for p in partes if p)
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", texto.lower()).strip("-")


def _numero_cl(texto: str) -> float:
    """'1.562' -> 1562 ; '14.4' (con sufijo M) -> 14.4"""
    if re.fullmatch(r"\d{1,3}(\.\d{3})+", texto):
        return float(texto.replace(".", ""))
    return float(texto.replace(",", "."))


def extraer_metricas(descripcion: str | None, cpl: int | None) -> dict[str, Any]:
    metricas: dict[str, Any] = {}
    if cpl is not None:
        metricas["cpl_promedio_clp"] = cpl
    if not descripcion:
        return metricas
    if m := re.search(r"([\d.]+)\s+leads", descripcion, re.IGNORECASE):
        metricas["leads"] = int(_numero_cl(m.group(1)))
    if m := re.search(r"\$\s*([\d.,]+)\s*M\b", descripcion):
        metricas["inversion_clp"] = int(round(_numero_cl(m.group(1)) * 1_000_000))
    if m := re.search(r"(\d+)\s+ventas", descripcion, re.IGNORECASE):
        metricas["ventas"] = int(m.group(1))
    if metricas.get("leads") and metricas.get("inversion_clp"):
        metricas["cpl_calculado_clp"] = round(metricas["inversion_clp"] / metricas["leads"])
    return metricas


def _cliente_desde_fuente(fuente: str | None) -> str | None:
    if fuente and (m := re.match(r"Caso\s+(.+?)\s+-", fuente, re.IGNORECASE)):
        return m.group(1).strip()
    return POR_CONFIRMAR


def _es_estimacion(fila: dict[str, Any]) -> bool:
    return "estimaci" in (fila.get("fuente") or "").lower()


def normalizar(fila: dict[str, Any], ruta: Path) -> dict[str, Any]:
    cliente = _cliente_desde_fuente(fila.get("fuente"))
    plataforma = fila.get("plataforma")
    creatividad = fila.get("mejor_creatividad")
    return {
        "slug": _slug(cliente or "mercado", fila.get("industria"), plataforma, creatividad),
        "cliente": cliente,
        "industria": fila.get("industria"),
        "plataforma": plataforma,
        "problema": POR_CONFIRMAR,  # La fuente no describe el problema del cliente.
        "solucion": (
            f"Campaña en {plataforma}; mejor creatividad: {creatividad}"
            if plataforma and creatividad else POR_CONFIRMAR
        ),
        "resultados": fila.get("descripcion"),
        "metricas": extraer_metricas(fila.get("descripcion"), fila.get("cpl_promedio_clp")),
        "fecha": POR_CONFIRMAR,  # La fuente solo indica el año (en el texto 'fuente').
        "fuente_archivo": str(ruta.relative_to(PROJECT_ROOT)),
        "tipo": "estimacion" if _es_estimacion(fila) else "real",
        # Compatibilidad con motor_ikki.py / dashboard.py
        "cpl_promedio_clp": fila.get("cpl_promedio_clp"),
        "mejor_creatividad": creatividad,
        "descripcion": fila.get("descripcion"),
        "fuente": fila.get("fuente"),
    }


def advertencias(caso: dict[str, Any]) -> list[str]:
    avisos = [f"{campo}: por confirmar" for campo in ("cliente", "problema", "fecha") if caso[campo] is None]
    m = caso["metricas"]
    if m.get("cpl_calculado_clp") and m.get("cpl_promedio_clp"):
        desvio = abs(m["cpl_calculado_clp"] - m["cpl_promedio_clp"]) / m["cpl_promedio_clp"]
        if desvio > 0.05:
            avisos.append(
                f"CPL inconsistente: declarado {m['cpl_promedio_clp']} vs "
                f"inversión/leads = {m['cpl_calculado_clp']} ({desvio:.0%})"
            )
    return avisos


def construir_casos(incluir_estimaciones: bool) -> list[dict[str, Any]]:
    casos: dict[str, dict[str, Any]] = {}
    for ruta in FUENTES:
        if not ruta.exists():
            log.warning("Fuente no encontrada: %s", ruta)
            continue
        for fila in leer_inserts(ruta):
            caso = normalizar(fila, ruta)
            if caso["tipo"] == "estimacion" and not incluir_estimaciones:
                log.info("Omitido (estimación, no caso real): %s", caso["slug"])
                continue
            casos[caso["slug"]] = caso  # dedupe local por slug
    return list(casos.values())


# ------------------------------------------------------------------ Supabase
def upsert_supabase(casos: list[dict[str, Any]]) -> int:
    from dotenv import load_dotenv
    from supabase import create_client

    load_dotenv(PROJECT_ROOT / ".env")
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise SystemExit("Faltan SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY en .env")
    client = create_client(url, key)
    respuesta = client.table(TABLA).upsert(casos, on_conflict="slug").execute()
    return len(respuesta.data or [])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--ejecutar", action="store_true", help="Escribe en Supabase (por defecto: dry-run).")
    parser.add_argument("--incluir-estimaciones", action="store_true", help="Incluye filas marcadas como estimación de mercado.")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    casos = construir_casos(args.incluir_estimaciones)
    modo = "EJECUCIÓN" if args.ejecutar else "DRY-RUN (sin tocar Supabase)"
    print(f"=== {modo}: {len(casos)} caso(s) para upsert en {TABLA} (on_conflict=slug) ===")
    for caso in casos:
        print(json.dumps(caso, ensure_ascii=False, indent=2))
        for aviso in advertencias(caso):
            print(f"  ⚠ {aviso}")

    if args.ejecutar and casos:
        n = upsert_supabase(casos)
        print(f"Upsert OK: {n} fila(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
