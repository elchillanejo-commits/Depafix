#!/usr/bin/env python3
"""Obrero Almacenes — captura ligera de relevamiento en terreno (DepaFix 3.0)."""

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "datos" / "obrero_almacenes"
CENTAVO = Decimal("0.01")


@dataclass
class Relevamiento:
    almacen: str
    comuna: str
    falla_dolor: str
    producto_competencia: str
    precio_clp: str
    fecha: str
    operador: str
    observaciones: str = ""


def _redondear(valor: Decimal) -> Decimal:
    return valor.quantize(CENTAVO, rounding=ROUND_HALF_UP)


def _clave(r: Relevamiento) -> str:
    return f"{r.almacen.strip().lower()}|{r.comuna.strip().lower()}|{r.fecha}"


def _validar(args) -> Relevamiento:
    almacen = (args.almacen or "").strip()
    comuna = (args.comuna or "").strip()
    falla = (args.falla_dolor or "").strip()
    producto = (args.producto_competencia or "").strip()
    operador = (args.operador or "").strip()
    fecha = (args.fecha or "").strip()

    if not almacen or len(almacen) < 2:
        raise ValueError("almacen requerido (min 2 chars)")
    if not comuna or len(comuna) < 2:
        raise ValueError("comuna requerida (min 2 chars)")
    if not falla:
        raise ValueError("falla_dolor requerido")
    if not producto:
        raise ValueError("producto_competencia requerido")
    if not operador:
        raise ValueError("operador requerido")
    try:
        fecha_obj = date.fromisoformat(fecha)
    except ValueError as exc:
        raise ValueError(f"fecha invalida (ISO YYYY-MM-DD): {fecha}") from exc
    if fecha_obj > date.today():
        raise ValueError("fecha no puede ser futura")

    try:
        precio = _redondear(Decimal(str(args.precio)))
    except Exception as exc:
        raise ValueError(f"precio invalido: {args.precio}") from exc
    if precio <= 0:
        raise ValueError("precio debe ser > 0")

    return Relevamiento(
        almacen=almacen,
        comuna=comuna,
        falla_dolor=falla,
        producto_competencia=producto,
        precio_clp=str(precio),
        fecha=fecha,
        operador=operador,
        observaciones=(args.observaciones or "").strip(),
    )


def _cargar() -> list[dict]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    archivo = DATA_DIR / "relevamientos.json"
    if not archivo.exists():
        return []
    try:
        return json.loads(archivo.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []


def _guardar(items: list[dict]) -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    archivo = DATA_DIR / "relevamientos.json"
    archivo.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    return archivo


def main() -> int:
    parser = argparse.ArgumentParser(prog="obrero_almacenes", description="Captura ligera de relevamiento de almacenes en terreno.")
    parser.add_argument("--almacen", required=True)
    parser.add_argument("--comuna", required=True)
    parser.add_argument("--falla-dolor", required=True, dest="falla_dolor")
    parser.add_argument("--producto-competencia", required=True, dest="producto_competencia")
    parser.add_argument("--precio", required=True)
    parser.add_argument("--fecha", required=True)
    parser.add_argument("--operador", required=True)
    parser.add_argument("--observaciones", default="")

    def _error(msg: str) -> None:
        parser.print_usage(sys.stderr)
        print(f"ERROR: {msg}", file=sys.stderr)
        sys.exit(1)

    parser.error = _error
    args = parser.parse_args()

    try:
        relevamiento = _validar(args)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    items = _cargar()
    clave = _clave(relevamiento)
    existente = next((i for i in items if i.get("_clave") == clave), None)

    if existente:
        existente.update(asdict(relevamiento))
        existente["_clave"] = clave
        accion = "ACTUALIZADO (idempotente)"
    else:
        nuevo = asdict(relevamiento)
        nuevo["_clave"] = clave
        items.append(nuevo)
        accion = "INSERTADO"

    archivo = _guardar(items)
    print(json.dumps({"accion": accion, "archivo": str(archivo), "relevamiento": asdict(relevamiento)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
