from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .catalogo_precios import (
    ITEMS,
    CalculoPresupuesto,
    calcular,
    construir_payload,
    formato_clp,
    item,
    linea_personalizada,
    totalizar,
)
from .config import DEFAULT_DB_PATH
from .db import (
    InspeccionTerreno,
    PresupuestoObra,
    calcular_proxima_mantencion,
    init_db,
)
from .presupuestador import construir_requerimientos

ESTADOS_CLI = {
    "COMPLETADA": "REALIZADA",
    "REALIZADA": "REALIZADA",
    "NO_ACCESO": "NO_ACCESO",
}
ESTADOS_PRESUPUESTO_BLOQUEADOS = {"APROBADO", "ENVIADO"}
ESTADO_SINCRONIZADO = "SINCRONIZADO"


@dataclass(frozen=True)
class ItemAdHoc:
    codigo: str
    desc: str
    cantidad: Decimal
    precio_unitario: Decimal
    costo_unitario: Decimal
    unidad: str


def _d(value: object) -> Decimal:
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"Valor decimal inválido: {value!r}") from exc


def _positive_decimal(value: str) -> Decimal:
    try:
        number = _d(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc
    if number <= 0:
        raise argparse.ArgumentTypeError("El valor debe ser mayor a cero.")
    return number


def _iso_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "Usa una fecha válida en formato YYYY-MM-DD."
        ) from exc


def _parse_item_extra(value: str) -> tuple[str, Decimal]:
    if ":" in value:
        codigo_raw, cantidad_raw = value.rsplit(":", 1)
    elif "=" in value:
        codigo_raw, cantidad_raw = value.rsplit("=", 1)
    else:
        raise argparse.ArgumentTypeError(
            "Formato esperado: CODIGO:CANTIDAD (ej. LED-001:2)."
        )
    codigo = codigo_raw.strip().upper()
    try:
        item(codigo)
    except KeyError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc
    try:
        cantidad = _d(cantidad_raw.strip())
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc
    if cantidad <= 0:
        raise argparse.ArgumentTypeError("La cantidad debe ser mayor a cero.")
    return codigo, cantidad


def _parse_item_adhoc(value: str) -> ItemAdHoc:
    parts = [part.strip() for part in value.split("|")]
    if len(parts) not in (5, 6):
        raise argparse.ArgumentTypeError(
            "Formato esperado: CODIGO|DESCRIPCION|CANTIDAD|PRECIO|COSTO[|UNIDAD]."
        )
    codigo, desc, cantidad_raw, precio_raw, costo_raw = parts[:5]
    unidad = parts[5] if len(parts) == 6 and parts[5] else "un"
    codigo = codigo.upper()
    if not re.fullmatch(r"[A-Z0-9][A-Z0-9._-]*", codigo):
        raise argparse.ArgumentTypeError(
            "El código ad-hoc solo admite letras, números, punto, guion y guion bajo."
        )
    if codigo in ITEMS:
        raise argparse.ArgumentTypeError(
            f"{codigo} existe en el catálogo; usa --item-extra {codigo}:CANTIDAD."
        )
    if not desc:
        raise argparse.ArgumentTypeError("La descripción ad-hoc no puede estar vacía.")
    try:
        cantidad = _d(cantidad_raw)
        precio = _d(precio_raw)
        costo = _d(costo_raw)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc
    if cantidad <= 0 or precio <= 0:
        raise argparse.ArgumentTypeError(
            "Cantidad y precio ad-hoc deben ser mayores a cero."
        )
    if costo < 0:
        raise argparse.ArgumentTypeError("El costo ad-hoc no puede ser negativo.")
    return ItemAdHoc(codigo, desc, cantidad, precio, costo, unidad or "un")


def _fmt_m2(value: object) -> str:
    if value is None:
        return "s/d"
    number = _d(value)
    if number == number.to_integral():
        return f"{int(number)} m²"
    return f"{number.normalize():f} m²"


def _as_datetime(value: date | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    return datetime.combine(value, time(12, 0), tzinfo=timezone.utc)


def _merge_unique(existing: list[str] | None, incoming: list[str]) -> list[str]:
    result = list(existing or [])
    for value in incoming:
        if value and value not in result:
            result.append(value)
    return result


def _append_note(existing: str | None, note: str, replace: bool) -> str:
    if replace or not existing:
        return note
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    return f"{existing.rstrip()}\n[{stamp}] {note}"


def _candidates(rows: list[InspeccionTerreno]) -> str:
    return "; ".join(f"{row.propiedad_id}: {row.direccion}" for row in rows)


def _buscar_inspeccion(
    session: Session,
    propiedad_id: str | None,
    direccion: str | None,
) -> InspeccionTerreno:
    if propiedad_id:
        rows = list(
            session.scalars(
                select(InspeccionTerreno).where(
                    InspeccionTerreno.propiedad_id == propiedad_id.strip()
                )
            )
        )
        if not rows:
            raise LookupError(f"No existe id_propiedad={propiedad_id!r}.")
        if len(rows) > 1:
            raise LookupError(
                f"id_propiedad={propiedad_id!r} tiene múltiples registros; "
                "corrige la base antes de continuar."
            )
        return rows[0]

    if not direccion:
        raise ValueError("Indica --id-propiedad o --direccion.")

    term = direccion.strip()
    exact = list(
        session.scalars(
            select(InspeccionTerreno).where(
                func.lower(InspeccionTerreno.direccion) == term.lower()
            )
        )
    )
    if len(exact) == 1:
        return exact[0]
    if len(exact) > 1:
        raise LookupError(
            f"La dirección {term!r} coincide con varias propiedades: "
            f"{_candidates(exact)}. Usa --id-propiedad."
        )

    partial = list(
        session.scalars(
            select(InspeccionTerreno).where(
                InspeccionTerreno.direccion.ilike(f"%{term}%")
            )
        )
    )
    if not partial:
        raise LookupError(f"No existe una propiedad que coincida con {term!r}.")
    if len(partial) > 1:
        raise LookupError(
            f"La dirección {term!r} es ambigua: {_candidates(partial)}. "
            "Usa --id-propiedad."
        )
    return partial[0]


def _actualizar_inspeccion(
    insp: InspeccionTerreno, args: argparse.Namespace
) -> list[str]:
    changes: list[str] = []

    if args.fecha:
        insp.fecha_inspeccion = _as_datetime(args.fecha)
        changes.append(f"fecha_inspeccion={args.fecha.isoformat()}")

    if args.estado:
        estado_db = ESTADOS_CLI[args.estado]
        insp.estado_visita = estado_db
        if insp.fecha_inspeccion is None:
            insp.fecha_inspeccion = _as_datetime(args.fecha)
        changes.append(f"estado={estado_db}" + (" (COMPLETADA)" if estado_db == "REALIZADA" else ""))

    if args.agua:
        insp.tipo_agua_caliente = args.agua
        changes.append(f"agua={args.agua}")

    if args.meses_mantencion is not None:
        insp.intervalo_mantencion_meses = args.meses_mantencion
        changes.append(f"meses_mantencion={args.meses_mantencion}")
        if args.fecha_ultima_mantencion:
            insp.fecha_ultima_mantencion_termo = args.fecha_ultima_mantencion
            insp.fecha_proxima_mantencion_termo = calcular_proxima_mantencion(
                args.fecha_ultima_mantencion, args.meses_mantencion
            )
            changes.append(
                f"proxima_mantencion={insp.fecha_proxima_mantencion_termo.isoformat()}"
            )
        elif insp.fecha_ultima_mantencion_termo:
            insp.fecha_proxima_mantencion_termo = calcular_proxima_mantencion(
                insp.fecha_ultima_mantencion_termo, args.meses_mantencion
            )
            changes.append(
                f"proxima_mantencion={insp.fecha_proxima_mantencion_termo.isoformat()}"
            )

    if args.m2_medidos is not None:
        insp.superficie_util_m2 = args.m2_medidos
        insp.m2_piso_spc = args.m2_medidos
        insp.requiere_piso_spc = True
        changes.append(f"m2_medidos={args.m2_medidos}")

    evidence_fields = {
        "fotos_antes": args.foto_antes,
        "fotos_despues": args.foto_despues,
        "videos_antes": args.video_antes,
        "videos_despues": args.video_despues,
    }
    for field, incoming in evidence_fields.items():
        if not incoming:
            continue
        current = getattr(insp, field) or []
        if args.reemplazar_evidencias:
            setattr(insp, field, list(incoming))
        else:
            setattr(insp, field, _merge_unique(current, incoming))
        changes.append(f"{field}={len(getattr(insp, field))}")

    if args.inspector:
        insp.inspector = args.inspector
        changes.append("inspector=actualizado")

    if args.notas:
        insp.observaciones = _append_note(
            insp.observaciones, args.notas, args.reemplazar_notas
        )
        changes.append("notas=actualizadas")

    return changes


def _presupuesto_actual(
    session: Session, insp: InspeccionTerreno
) -> PresupuestoObra | None:
    return session.scalars(
        select(PresupuestoObra)
        .where(PresupuestoObra.inspeccion_id == insp.id)
        .order_by(PresupuestoObra.id.desc())
        .limit(1)
    ).first()


def _preparar_lineas_extra(
    calculo_base: CalculoPresupuesto, adhoc: list[ItemAdHoc]
) -> tuple[list[Any], list[str]]:
    lines = list(calculo_base.lineas)
    codes = {line.codigo for line in lines}
    warnings: list[str] = []
    for extra in adhoc:
        if extra.codigo in codes:
            raise ValueError(f"Código ad-hoc duplicado: {extra.codigo}.")
        if extra.costo_unitario == 0:
            warnings.append(
                f"{extra.codigo} no tiene costo mayorista; el margen se calcula con costo 0."
            )
        lines.append(
            linea_personalizada(
                codigo=extra.codigo,
                desc=extra.desc,
                cantidad=extra.cantidad,
                precio_unitario=extra.precio_unitario,
                costo_unitario=extra.costo_unitario,
                unidad=extra.unidad,
            )
        )
        codes.add(extra.codigo)
    return lines, warnings


def _recalcular_presupuesto(
    insp: InspeccionTerreno,
    presupuesto: PresupuestoObra,
    args: argparse.Namespace,
) -> tuple[CalculoPresupuesto, list[str]]:
    if (
        presupuesto.estado in ESTADOS_PRESUPUESTO_BLOQUEADOS
        or presupuesto.sync_status == ESTADO_SINCRONIZADO
    ) and not args.forzar_medicion:
        raise ValueError(
            "El presupuesto está aprobado/enviado o ya sincronizado. "
            "Usa --forzar-medicion para recalcularlo y reiniciar su sincronización."
        )

    requerimientos, pendiente = construir_requerimientos(insp)
    for codigo, cantidad in args.item_extra or []:
        requerimientos[codigo] = requerimientos.get(codigo, Decimal("0")) + cantidad

    calculo_base = calcular(requerimientos)
    lineas, warnings = _preparar_lineas_extra(calculo_base, args.item_adhoc or [])
    calculo = totalizar(lineas)

    if presupuesto.estado in ESTADOS_PRESUPUESTO_BLOQUEADOS:
        presupuesto.estado = "BORRADOR"
    if presupuesto.sync_status == ESTADO_SINCRONIZADO or args.forzar_medicion:
        presupuesto.sync_status = "NO_SINCRONIZADO"
        presupuesto.uuid_railway = None
        presupuesto.railway_response = None
        presupuesto.synced_at = None
        presupuesto.sync_error = None

    m2 = _d(insp.superficie_util_m2)
    presupuesto.fecha_emision = date.today()
    presupuesto.moneda = "CLP"
    presupuesto.neto = calculo.total_neto
    presupuesto.iva = Decimal("0")
    presupuesto.total = calculo.total_neto
    presupuesto.partidas = calculo.partidas()
    presupuesto.costo_mayorista = calculo.costo_mayorista
    presupuesto.comision_corredor = calculo.comision_corredor
    presupuesto.margen_depafix = calculo.margen_depafix
    presupuesto.estado_medicion = "PENDIENTE_MEDICION" if pendiente else "MEDIDO"
    presupuesto.payload_json = construir_payload(
        insp.direccion, insp.comuna or "Santiago", calculo
    )
    if pendiente:
        presupuesto.observaciones = (
            "Recalculado en gestión de visita. Superficie referencial 35 m²; "
            "falta medición real."
        )
    else:
        presupuesto.observaciones = (
            f"Recalculado en gestión de visita. Superficie medida: {_fmt_m2(m2)}."
        )
    for warning in warnings:
        presupuesto.observaciones = f"{presupuesto.observaciones} {warning}"
    return calculo, warnings


def _aprobar_presupuesto(
    insp: InspeccionTerreno,
    presupuesto: PresupuestoObra,
    args: argparse.Namespace,
) -> bool:
    if presupuesto.estado == "APROBADO":
        return False

    pendiente = (
        presupuesto.estado_medicion == "PENDIENTE_MEDICION"
        or _d(insp.superficie_util_m2) <= 0
    )
    if pendiente and not args.forzar_medicion:
        raise ValueError(
            "No se puede aprobar: el presupuesto sigue en PENDIENTE_MEDICION. "
            "Mide en terreno o usa --forzar-medicion de forma explícita."
        )
    presupuesto.estado = "APROBADO"
    if presupuesto.fecha_emision is None:
        presupuesto.fecha_emision = date.today()
    if pendiente:
        presupuesto.observaciones = _append_note(
            presupuesto.observaciones,
            "Aprobado con medición pendiente por decisión explícita (--forzar-medicion).",
            False,
        )
    return True


def _print_summary(
    insp: InspeccionTerreno,
    presupuesto: PresupuestoObra | None,
    calculo: CalculoPresupuesto | None,
    dry_run: bool,
    verbose: bool,
    warnings: list[str],
) -> None:
    prefix = "[DRY-RUN] " if dry_run else ""
    estado = insp.estado_visita
    if estado == "REALIZADA":
        estado = "REALIZADA (COMPLETADA)"
    print(f"{prefix}INSPECCION {insp.propiedad_id} | {insp.direccion}")
    print(
        f"  estado={estado} | agua={insp.tipo_agua_caliente} | "
        f"meses_termo={insp.intervalo_mantencion_meses or 's/d'} | "
        f"m2={_fmt_m2(insp.superficie_util_m2)}"
    )
    print(
        "  evidencias: "
        f"fotos_antes={len(insp.fotos_antes or [])} "
        f"fotos_despues={len(insp.fotos_despues or [])} "
        f"videos_antes={len(insp.videos_antes or [])} "
        f"videos_despues={len(insp.videos_despues or [])}"
    )
    if verbose and insp.observaciones:
        print(f"  notas={insp.observaciones}")
    for warning in warnings:
        print(f"  ADVERTENCIA: {warning}")

    if presupuesto is not None:
        print(
            f"  PRESUPUESTO id={presupuesto.id} estado={presupuesto.estado} "
            f"medicion={presupuesto.estado_medicion} "
            f"total={formato_clp(presupuesto.total)} "
            f"comision={formato_clp(presupuesto.comision_corredor)} "
            f"margen={formato_clp(presupuesto.margen_depafix)}"
        )
        print(
            f"  sync={presupuesto.sync_status} uuid={presupuesto.uuid_railway or '-'}"
        )
    if calculo is not None:
        partidas = ", ".join(
            f"{linea.codigo}:{linea.cantidad.normalize():f}" for linea in calculo.lineas
        )
        print(f"  partidas={partidas}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Registra la visita en terreno, recalcula el presupuesto con m² reales "
            "e ítems extra, y permite aprobarlo para sync_railway."
        )
    )
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument(
        "--id-propiedad",
        "--id",
        dest="propiedad_id",
        help="ID de propiedad (columna propiedad_id).",
    )
    target.add_argument(
        "--direccion",
        help="Dirección exacta o parcial; debe ser única.",
    )
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH, help="Ruta SQLite.")
    parser.add_argument(
        "--estado",
        type=str.upper,
        choices=sorted(ESTADOS_CLI),
        help="COMPLETADA (se guarda como REALIZADA) o NO_ACCESO.",
    )
    parser.add_argument(
        "--agua",
        type=str.upper,
        choices=["TERMO_ELECTRICO", "CALEFONT", "CALDERA_CENTRAL"],
        help="Tipo de agua caliente observado.",
    )
    parser.add_argument(
        "--meses-mantencion",
        type=int,
        choices=[6, 12],
        help="Intervalo de mantención del termo: 6 o 12 meses.",
    )
    parser.add_argument(
        "--fecha-ultima-mantencion",
        type=_iso_date,
        help="Fecha de última mantención del termo (YYYY-MM-DD).",
    )
    parser.add_argument(
        "--m2-medidos",
        type=_positive_decimal,
        help="Superficie real medida en terreno; recalcula SPC-001.",
    )
    parser.add_argument("--foto-antes", action="append", default=[], help="Ruta foto antes; repetible.")
    parser.add_argument("--foto-despues", action="append", default=[], help="Ruta foto después; repetible.")
    parser.add_argument("--video-antes", action="append", default=[], help="Ruta video antes; repetible.")
    parser.add_argument("--video-despues", action="append", default=[], help="Ruta video después; repetible.")
    parser.add_argument(
        "--validar-evidencias",
        action="store_true",
        help="Falla si alguna ruta de evidencia no existe localmente.",
    )
    parser.add_argument(
        "--reemplazar-evidencias",
        action="store_true",
        help="Reemplaza las listas de evidencias en vez de agregar.",
    )
    parser.add_argument("--notas", help="Nota técnica de la visita.")
    parser.add_argument(
        "--reemplazar-notas",
        action="store_true",
        help="Reemplaza observaciones en vez de agregar una nota fechada.",
    )
    parser.add_argument("--inspector", help="Nombre o identificador del inspector.")
    parser.add_argument(
        "--fecha",
        type=_iso_date,
        help="Fecha de inspección (YYYY-MM-DD); por defecto ahora.",
    )
    parser.add_argument(
        "--item-extra",
        action="append",
        type=_parse_item_extra,
        default=[],
        metavar="CODIGO:CANTIDAD",
        help="Ítem adicional del catálogo; repetible.",
    )
    parser.add_argument(
        "--item-adhoc",
        action="append",
        type=_parse_item_adhoc,
        default=[],
        metavar="CODIGO|DESC|CANTIDAD|PRECIO|COSTO[|UNIDAD]",
        help="Partida ad-hoc; repetible.",
    )
    parser.add_argument(
        "--recalcular",
        action="store_true",
        help="Recalcula el presupuesto aunque no se cambie el m².",
    )
    parser.add_argument(
        "--aprobar",
        action="store_true",
        help="Marca el presupuesto como APROBADO.",
    )
    parser.add_argument(
        "--forzar-medicion",
        action="store_true",
        help=(
            "Permite aprobar con PENDIENTE_MEDICION o recalcular un presupuesto "
            "aprobado/sincronizado. Úsalo de forma explícita."
        ),
    )
    parser.add_argument("--dry-run", action="store_true", help="Muestra cambios sin guardar.")
    parser.add_argument("--verbose", action="store_true", help="Muestra notas y detalles.")
    return parser


def _evidence_paths(args: argparse.Namespace) -> list[str]:
    return [
        *args.foto_antes,
        *args.foto_despues,
        *args.video_antes,
        *args.video_despues,
    ]


def _validar_evidencias(args: argparse.Namespace) -> None:
    missing = [
        path
        for path in _evidence_paths(args)
        if not Path(path).expanduser().exists()
    ]
    if missing:
        raise ValueError(
            "Rutas de evidencia inexistentes: " + ", ".join(missing)
        )


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    recalc = bool(
        args.recalcular
        or args.m2_medidos is not None
        or args.item_extra
        or args.item_adhoc
    )
    has_update = bool(
        args.estado
        or args.agua
        or args.meses_mantencion is not None
        or args.fecha_ultima_mantencion
        or args.m2_medidos is not None
        or args.foto_antes
        or args.foto_despues
        or args.video_antes
        or args.video_despues
        or args.notas
        or args.inspector
        or args.fecha
    )
    if not has_update and not recalc and not args.aprobar:
        parser.error(
            "Indica al menos una actualización, --recalcular o --aprobar."
        )
    if args.validar_evidencias:
        _validar_evidencias(args)

    try:
        engine = init_db(f"sqlite:///{args.db}")
        with Session(engine) as session:
            insp = _buscar_inspeccion(
                session, args.propiedad_id, args.direccion
            )
            changes = _actualizar_inspeccion(insp, args)
            presupuesto = _presupuesto_actual(session, insp)
            calculo: CalculoPresupuesto | None = None
            warnings: list[str] = []

            if recalc:
                if presupuesto is None:
                    raise LookupError(
                        f"La propiedad {insp.propiedad_id} no tiene presupuesto; "
                        "genera primero uno con presupuestador."
                    )
                calculo, warnings = _recalcular_presupuesto(
                    insp, presupuesto, args
                )
            if args.aprobar:
                if presupuesto is None:
                    raise LookupError(
                        f"La propiedad {insp.propiedad_id} no tiene presupuesto; "
                        "genera primero uno con presupuestador."
                    )
                _aprobar_presupuesto(insp, presupuesto, args)

            if args.dry_run:
                session.flush()
                _print_summary(
                    insp,
                    presupuesto,
                    calculo,
                    True,
                    args.verbose,
                    warnings,
                )
                if changes:
                    print("  cambios=" + ", ".join(changes))
                session.rollback()
                print("DRY-RUN: cambios no guardados.")
                return 0

            session.commit()
            session.refresh(insp)
            if presupuesto is not None:
                session.refresh(presupuesto)
            _print_summary(
                insp,
                presupuesto,
                calculo,
                False,
                args.verbose,
                warnings,
            )
            if changes:
                print("  cambios=" + ", ".join(changes))
            print("GESTION_OK")
            return 0
    except (LookupError, ValueError, KeyError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
