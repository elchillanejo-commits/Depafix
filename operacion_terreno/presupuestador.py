from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from operacion_terreno.uf_provider import obtener_uf_vigente
from pathlib import Path
from typing import Iterable

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from .catalogo_precios import (
    COMISION_CORREDOR,
    CalculoPresupuesto,
    calcular,
    construir_payload,
    formato_clp,
)
from .config import DEFAULT_DB_PATH, PROJECT_ROOT
from .db import InspeccionTerreno, PresupuestoObra, init_db

ESTADO_SIMULACION = "SIMULACION_CORREDOR"
SUPERFICIE_REFERENCIAL_M2 = Decimal("35")
DEFAULT_REPORT_PATH = PROJECT_ROOT / "PROPUESTA_COMERCIAL_CORREDOR.md"
MONEY_QUANT = Decimal("1")


@dataclass
class PresupuestoGenerado:
    inspeccion: InspeccionTerreno
    calculo: CalculoPresupuesto
    presupuesto: PresupuestoObra
    medicion_pendiente: bool


def _d(value: object) -> Decimal:
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _entero(value: object) -> int:
    return int(_d(value))


def _texto_medicion(calculo: CalculoPresupuesto, pendiente: bool) -> str:
    if pendiente:
        return (
            "Superficie referencial de 35 m²; confirmar medición en terreno antes "
            "de enviar el presupuesto definitivo."
        )
    return (
        f"Superficie declarada: {calculo.lineas[0].cantidad.normalize():f} m². "
        "Confirmar medidas y condiciones del inmueble en visita."
    )


def construir_requerimientos(insp: InspeccionTerreno) -> tuple[dict[str, Decimal], bool]:
    es_vacante = bool(insp.es_vacante or insp.estado_propiedad == "Vacante")
    superficie = _d(insp.superficie_util_m2)
    pendiente = superficie <= 0
    m2 = SUPERFICIE_REFERENCIAL_M2 if pendiente else superficie

    requerimientos: dict[str, Decimal] = {}
    if insp.requiere_piso_spc or es_vacante:
        requerimientos["SPC-001"] = m2
    if _entero(insp.plafones_led) > 0:
        requerimientos["LED-001"] = Decimal(_entero(insp.plafones_led))
    if _entero(insp.enchufes) > 0:
        requerimientos["ELE-001"] = Decimal(_entero(insp.enchufes))
    if _entero(insp.soporte_tv) > 0:
        requerimientos["TV-001"] = Decimal(_entero(insp.soporte_tv))
    if es_vacante or insp.tipo_agua_caliente == "TERMO_ELECTRICO":
        requerimientos["TER-001"] = Decimal("1")
    if es_vacante:
        requerimientos["SIL-001"] = Decimal("1")
    return requerimientos, pendiente


def _seleccionar(
    session: Session, ids: Iterable[str] | None = None
) -> list[InspeccionTerreno]:
    query = select(InspeccionTerreno).where(
        or_(
            InspeccionTerreno.es_vacante.is_(True),
            InspeccionTerreno.estado_propiedad == "Vacante",
        )
    )
    if ids:
        query = query.where(InspeccionTerreno.propiedad_id.in_(list(ids)))
    query = query.order_by(
        InspeccionTerreno.prioridad_ready_to_rent.asc(),
        InspeccionTerreno.score_ready_to_rent.desc(),
        InspeccionTerreno.propiedad_id.asc(),
    )
    return list(session.scalars(query))


def _presupuesto_existente(
    session: Session, inspeccion_id: int
) -> PresupuestoObra | None:
    return session.scalars(
        select(PresupuestoObra)
        .where(
            PresupuestoObra.inspeccion_id == inspeccion_id,
            PresupuestoObra.estado == ESTADO_SIMULACION,
        )
        .order_by(PresupuestoObra.id.desc())
        .limit(1)
    ).first()


def _presupuesto_no_simulacion(
    session: Session, inspeccion_id: int
) -> PresupuestoObra | None:
    return session.scalars(
        select(PresupuestoObra)
        .where(
            PresupuestoObra.inspeccion_id == inspeccion_id,
            PresupuestoObra.estado != ESTADO_SIMULACION,
        )
        .order_by(PresupuestoObra.id.desc())
        .limit(1)
    ).first()


def generar_presupuestos_simulacion(
    db_path: Path = DEFAULT_DB_PATH,
    output_path: Path | None = DEFAULT_REPORT_PATH,
    ids: Iterable[str] | None = None,
) -> list[PresupuestoGenerado]:
    engine = init_db(f"sqlite:///{db_path}")
    generados: list[PresupuestoGenerado] = []

    with Session(engine) as session:
        inspecciones = _seleccionar(session, ids)
        if not inspecciones:
            raise ValueError(
                "No hay propiedades marcadas como vacantes. Ejecuta primero el pipeline "
                "para sembrar las inspecciones."
            )

        for insp in inspecciones:
            bloqueado = _presupuesto_no_simulacion(session, insp.id)
            if bloqueado is not None:
                raise ValueError(
                    f"La propiedad {insp.propiedad_id} ya tiene presupuesto "
                    f"{bloqueado.estado} (id={bloqueado.id}); no se genera una nueva "
                    "simulación. Usa --id para procesar solo las vacantes sin "
                    "presupuesto o en SIMULACION_CORREDOR, o actualiza la unidad "
                    "con gestion_visita."
                )

            requerimientos, pendiente = construir_requerimientos(insp)
            calculo = calcular(requerimientos)
            payload = construir_payload(insp.direccion, insp.comuna, calculo)

            presupuesto = _presupuesto_existente(session, insp.id)
            if presupuesto is None:
                presupuesto = PresupuestoObra(
                    inspeccion_id=insp.id,
                    propiedad_id=insp.propiedad_id,
                    estado=ESTADO_SIMULACION,
                )
                session.add(presupuesto)

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
            presupuesto.payload_json = payload
            presupuesto.observaciones = _texto_medicion(calculo, pendiente)
            presupuesto.sync_status = "NO_SINCRONIZADO"
            presupuesto.sync_error = None
            presupuesto.uuid_railway = None
            presupuesto.railway_response = None
            presupuesto.synced_at = None

            session.flush()
            generados.append(
                PresupuestoGenerado(
                    inspeccion=insp,
                    calculo=calculo,
                    presupuesto=presupuesto,
                    medicion_pendiente=pendiente,
                )
            )

        session.commit()
        for generado in generados:
            session.refresh(generado.presupuesto)
            session.refresh(generado.inspeccion)

    if output_path is not None:
        output_path.write_text(render_reporte(generados), encoding="utf-8")
    return generados


def _m2_texto(valor: object) -> str:
    if valor is None:
        return "s/d"
    numero = _d(valor)
    if numero == numero.to_integral():
        return f"{int(numero)} m²"
    return f"{numero.normalize():f} m²"


def _dormitorios_texto(insp: InspeccionTerreno) -> str:
    if insp.dormitorios is None and insp.banos is None:
        return "s/d"
    dorm = "s/d" if insp.dormitorios is None else str(insp.dormitorios)
    banos = "s/d" if insp.banos is None else str(insp.banos)
    return f"{dorm}D/{banos}B"


def render_reporte(generados: list[PresupuestoGenerado]) -> str:
    total_costo = sum((g.calculo.costo_mayorista for g in generados), Decimal("0"))
    total_venta = sum((g.calculo.total_neto for g in generados), Decimal("0"))
    total_comision = sum((g.calculo.comision_corredor for g in generados), Decimal("0"))
    total_margen = sum((g.calculo.margen_depafix for g in generados), Decimal("0"))
    margen_pct = (
        (total_margen / total_venta * 100).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
        if total_venta
        else Decimal("0")
    )
    pendientes = sum(1 for g in generados if g.medicion_pendiente)

    lines = [
        "# Propuesta Comercial — Corredor Santiago Centro",
        "",
        f"**Fecha:** {date.today().isoformat()}  ",
        f"**Unidades incluidas:** {len(generados)}  ",
        f"**Unidades con medición pendiente:** {pendientes}  ",
        "**Moneda:** CLP neto. **Comisión corredor:** 10% sobre venta neta.",
        "",
        "## Resumen financiero",
        "",
        "| ID | Dirección | m² | Dorm/Baños | Prioridad | Medición | Costo mayorista | Venta neta | Comisión 10% | Margen DepaFix | Margen % |",
        "|---|---|---:|---|---|---|---:|---:|---:|---:|---:|",
    ]
    for g in generados:
        insp = g.inspeccion
        lines.append(
            "| {id} | {direccion} | {m2} | {dorm} | {prioridad} | {medicion} | {costo} | {venta} | {comision} | {margen} | {pct}% |".format(
                id=insp.propiedad_id,
                direccion=(insp.direccion or "").replace("|", "/"),
                m2=_m2_texto(insp.superficie_util_m2),
                dorm=_dormitorios_texto(insp),
                prioridad=insp.prioridad_ready_to_rent or "s/d",
                medicion="Pendiente" if g.medicion_pendiente else "Medida",
                costo=formato_clp(g.calculo.costo_mayorista),
                venta=formato_clp(g.calculo.total_neto),
                comision=formato_clp(g.calculo.comision_corredor),
                margen=formato_clp(g.calculo.margen_depafix),
                pct=f"{g.calculo.margen_depafix_pct:.1f}",
            )
        )
    lines.extend(
        [
            f"| **TOTAL** | **{len(generados)} unidades** |  |  |  |  | **{formato_clp(total_costo)}** | **{formato_clp(total_venta)}** | **{formato_clp(total_comision)}** | **{formato_clp(total_margen)}** | **{margen_pct:.1f}%** |",
            "",
            "## Detalle por unidad",
            "",
        ]
    )

    for g in generados:
        insp = g.inspeccion
        lines.extend(
            [
                f"### {insp.propiedad_id} — {insp.direccion}",
                "",
                f"- Superficie: {_m2_texto(insp.superficie_util_m2)}"
                + (" (referencial 35 m²; pendiente de medición)" if g.medicion_pendiente else ""),
                f"- Dormitorios/baños: {_dormitorios_texto(insp)}",
                f"- Prioridad Ready-to-Rent: {insp.prioridad_ready_to_rent or 's/d'}"
                + (f" (score {insp.score_ready_to_rent})" if insp.score_ready_to_rent is not None else ""),
                f"- Estado de medición: {'PENDIENTE_MEDICION' if g.medicion_pendiente else 'MEDIDO'}",
                "",
                "| Ítem | Cantidad | Precio unitario | Subtotal |",
                "|---|---:|---:|---:|",
            ]
        )
        for linea in g.calculo.lineas:
            lines.append(
                f"| {linea.codigo} — {linea.desc.split(' - ', 1)[-1]} | "
                f"{linea.cantidad.normalize():f} {linea.unidad} | "
                f"{formato_clp(linea.precio_unitario)} | {formato_clp(linea.subtotal_neto)} |"
            )
        lines.extend(
            [
                "",
                f"**Costo mayorista:** {formato_clp(g.calculo.costo_mayorista)}  ",
                f"**Venta neta:** {formato_clp(g.calculo.total_neto)}  ",
                f"**Comisión corredor (10%):** {formato_clp(g.calculo.comision_corredor)}  ",
                f"**Margen DepaFix:** {formato_clp(g.calculo.margen_depafix)} "
                f"({g.calculo.margen_depafix_pct:.1f}%)",
                "",
            ]
        )

    lineas_whatsapp = [
        "Resumen para WhatsApp:",
        f"Propiedades Ready-to-Rent priorizadas: {len(generados)}",
        f"Costo mayorista total: {formato_clp(total_costo)}",
        f"Venta neta total: {formato_clp(total_venta)}",
        f"Comisión corredor (10%): {formato_clp(total_comision)}",
        f"Margen DepaFix: {formato_clp(total_margen)} ({margen_pct:.1f}%)",
    ]
    if pendientes:
        lineas_whatsapp.append(
            f"Unidades con medición pendiente: {pendientes} (superficie referencial 35 m²)"
        )
    lines.extend(
        [
            "## Resumen para WhatsApp",
            "",
            "```text",
            *lineas_whatsapp,
            "```",
            "",
            "## Notas de alcance",
            "",
            "- Precios netos en CLP; no incluyen IVA ni gastos no especificados.",
            "- La comisión del corredor se calcula como 10% de la venta neta.",
            "- Los presupuestos con `PENDIENTE_MEDICION` usan 35 m² referenciales; "
            "deben confirmarse antes de enviar una propuesta definitiva.",
            "- No se incluyen RUT, correos, teléfonos ni nombres de propietarios/arrendatarios.",
            "- Los presupuestos se guardan en estado `SIMULACION_CORREDOR`; no se envían a "
            "Railway hasta que un humano los revise y los marque como `APROBADO`.",
            "",
        ]
    )
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Genera presupuestos de simulación para las vacantes Ready-to-Rent "
            "y escribe el reporte comercial del corredor."
        )
    )
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH, help="Ruta SQLite.")
    parser.add_argument(
        "--report",
        type=Path,
        default=None,
        help=(
            "Ruta del reporte Markdown de salida. Por defecto se escribe "
            "PROPUESTA_COMERCIAL_CORREDOR.md solo cuando no se usa --id."
        ),
    )
    parser.add_argument(
        "--id",
        action="append",
        dest="ids",
        help="propiedad_id a presupuestar; repetible. Por defecto, todas las vacantes.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report_path = args.report
    if report_path is None and not args.ids:
        report_path = DEFAULT_REPORT_PATH
    try:
        generados = generar_presupuestos_simulacion(
            db_path=args.db, output_path=report_path, ids=args.ids
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(f"Presupuestos generados: {len(generados)}")
    for generado in generados:
        insp = generado.inspeccion
        print(
            f"- {insp.propiedad_id} | {insp.direccion} | "
            f"venta={formato_clp(generado.calculo.total_neto)} | "
            f"comisión={formato_clp(generado.calculo.comision_corredor)} | "
            f"margen={formato_clp(generado.calculo.margen_depafix)} | "
            f"{generado.presupuesto.estado_medicion}"
        )
    if report_path is not None:
        print(f"Reporte: {report_path}")
    else:
        print("Reporte: no generado para subconjunto; usa --report RUTA para forzarlo.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
