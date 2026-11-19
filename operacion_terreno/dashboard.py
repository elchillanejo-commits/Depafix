from __future__ import annotations

import argparse
import html
import json
import sqlite3
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Iterable, Sequence
from urllib.parse import urlparse

from .catalogo_precios import formato_clp
from .config import DEFAULT_DB_PATH, DEFAULT_ROUTES_JSON

ESTADOS_INSPECCION = ("PENDIENTE", "REALIZADA", "NO_ACCESO", "NO_APLICA")
ESTADOS_FINANCIEROS = ("SIMULACION_CORREDOR", "APROBADO", "SINCRONIZADO")
MATERIALES = (
    ("SPC-001", "Piso SPC", "m²"),
    ("LED-001", "Plafones LED", "un"),
    ("ELE-001", "Enchufes/interruptores", "un"),
    ("TV-001", "Soportes TV", "un"),
    ("TER-001", "Mantenciones de termo", "un"),
    ("SIL-001", "Sellados de silicona", "gl"),
)
ROI_UPLIFT_MENSUAL = Decimal("50000")
ROI_UPLIFT_TEXTO = "Supuesto conservador de +$50.000/mes por unidad, basado en la ficha SPC."
ZERO = Decimal("0")


@dataclass(frozen=True)
class Inspeccion:
    id: int
    propiedad_id: str
    direccion: str
    estado_visita: str
    tipo_agua: str
    intervalo_mantencion: int | None
    superficie_m2: Decimal | None
    dormitorios: int | None
    banos: int | None
    prioridad: str | None
    score: int
    es_vacante: bool
    estado_propiedad: str | None
    segmento_ruta: str | None
    parada_ruta: int | None


@dataclass(frozen=True)
class Presupuesto:
    id: int
    inspeccion_id: int
    propiedad_id: str
    estado: str
    estado_medicion: str
    total: Decimal
    costo: Decimal
    comision: Decimal
    margen: Decimal
    sync_status: str
    partidas: tuple[dict[str, Any], ...]

    @property
    def m2_spc(self) -> Decimal:
        for partida in self.partidas:
            if partida.get("codigo") == "SPC-001":
                return _d(partida.get("cantidad"))
        return ZERO


@dataclass(frozen=True)
class Ruta:
    bloque: str
    segmento: str
    paradas: int
    unidades: int
    primera_parada: str
    ultima_parada: str
    waypoints: int
    url: str


@dataclass(frozen=True)
class BucketFinanciero:
    nombre: str
    cantidad: int
    costo: Decimal
    venta: Decimal
    comision: Decimal
    margen: Decimal


def _d(value: object) -> Decimal:
    if value is None:
        return ZERO
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _d_opt(value: object) -> Decimal | None:
    if value is None:
        return None
    return _d(value)


def _int_opt(value: object) -> int | None:
    if value is None:
        return None
    return int(value)


def _texto(value: object, default: str = "s/d") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text or default


def _json_partidas(raw: object) -> tuple[dict[str, Any], ...]:
    if not raw:
        return ()
    try:
        parsed = json.loads(str(raw))
    except (TypeError, ValueError):
        return ()
    if not isinstance(parsed, list):
        return ()
    return tuple(item for item in parsed if isinstance(item, dict))


def _conectar_ro(path: Path) -> sqlite3.Connection:
    uri = f"{path.resolve().as_uri()}?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only = ON")
    return connection


def _cargar_inspecciones(connection: sqlite3.Connection) -> list[Inspeccion]:
    rows = connection.execute(
        """
        SELECT id, propiedad_id, direccion, estado_visita, tipo_agua_caliente,
               intervalo_mantencion_meses, superficie_util_m2, dormitorios, banos,
               prioridad_ready_to_rent, score_ready_to_rent, es_vacante,
               estado_propiedad, segmento_ruta, parada_ruta
        FROM inspecciones_terreno
        ORDER BY id
        """
    ).fetchall()
    return [
        Inspeccion(
            id=int(row["id"]),
            propiedad_id=str(row["propiedad_id"]),
            direccion=str(row["direccion"]),
            estado_visita=str(row["estado_visita"]),
            tipo_agua=str(row["tipo_agua_caliente"] or "SIN_INFORMACION"),
            intervalo_mantencion=_int_opt(row["intervalo_mantencion_meses"]),
            superficie_m2=_d_opt(row["superficie_util_m2"]),
            dormitorios=_int_opt(row["dormitorios"]),
            banos=_int_opt(row["banos"]),
            prioridad=row["prioridad_ready_to_rent"],
            score=int(row["score_ready_to_rent"] or 0),
            es_vacante=bool(row["es_vacante"]),
            estado_propiedad=row["estado_propiedad"],
            segmento_ruta=row["segmento_ruta"],
            parada_ruta=_int_opt(row["parada_ruta"]),
        )
        for row in rows
    ]


def _cargar_presupuestos(connection: sqlite3.Connection) -> list[Presupuesto]:
    rows = connection.execute(
        """
        SELECT id, inspeccion_id, propiedad_id, estado, estado_medicion, total,
               costo_mayorista, comision_corredor, margen_depafix, sync_status,
               partidas
        FROM presupuestos_obra
        ORDER BY id
        """
    ).fetchall()
    return [
        Presupuesto(
            id=int(row["id"]),
            inspeccion_id=int(row["inspeccion_id"]),
            propiedad_id=str(row["propiedad_id"]),
            estado=str(row["estado"]),
            estado_medicion=str(row["estado_medicion"]),
            total=_d(row["total"]),
            costo=_d(row["costo_mayorista"]),
            comision=_d(row["comision_corredor"]),
            margen=_d(row["margen_depafix"]),
            sync_status=str(row["sync_status"]),
            partidas=_json_partidas(row["partidas"]),
        )
        for row in rows
    ]


def _cargar_rutas(path: Path) -> list[Ruta]:
    with path.open(encoding="utf-8") as file:
        raw = json.load(file)
    if not isinstance(raw, list):
        raise ValueError(f"{path} debe contener una lista de rutas.")
    rutas: list[Ruta] = []
    for index, route in enumerate(raw, start=1):
        if not isinstance(route, dict):
            raise ValueError(f"Ruta #{index} inválida en {path}.")
        url = _texto(route.get("url"), "")
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            raise ValueError(f"Ruta #{index} no tiene una URL http(s) válida.")
        rutas.append(
            Ruta(
                bloque=_texto(route.get("bloque")),
                segmento=_texto(route.get("segmento")),
                paradas=int(route.get("paradas") or 0),
                unidades=int(route.get("unidades") or 0),
                primera_parada=_texto(route.get("primer_parada")),
                ultima_parada=_texto(route.get("ultima_parada")),
                waypoints=int(route.get("waypoints") or 0),
                url=url,
            )
        )
    return rutas


def _presupuestos_actuales(presupuestos: Iterable[Presupuesto]) -> list[Presupuesto]:
    actuales: dict[int, Presupuesto] = {}
    for presupuesto in presupuestos:
        actuales[presupuesto.inspeccion_id] = presupuesto
    return sorted(actuales.values(), key=lambda item: item.id)


def _bucket_financiero(presupuesto: Presupuesto) -> str:
    if presupuesto.sync_status == "SINCRONIZADO":
        return "SINCRONIZADO"
    return presupuesto.estado or "SIN_ESTADO"


def _resumen_financiero(presupuestos: Iterable[Presupuesto]) -> list[BucketFinanciero]:
    buckets: dict[str, dict[str, object]] = {}
    for presupuesto in presupuestos:
        nombre = _bucket_financiero(presupuesto)
        bucket = buckets.setdefault(
            nombre,
            {
                "cantidad": 0,
                "costo": ZERO,
                "venta": ZERO,
                "comision": ZERO,
                "margen": ZERO,
            },
        )
        bucket["cantidad"] = int(bucket["cantidad"]) + 1
        bucket["costo"] = _d(bucket["costo"]) + presupuesto.costo
        bucket["venta"] = _d(bucket["venta"]) + presupuesto.total
        bucket["comision"] = _d(bucket["comision"]) + presupuesto.comision
        bucket["margen"] = _d(bucket["margen"]) + presupuesto.margen

    ordered = list(ESTADOS_FINANCIEROS) + sorted(
        set(buckets) - set(ESTADOS_FINANCIEROS)
    )
    return [
        BucketFinanciero(
            nombre=nombre,
            cantidad=int(buckets.get(nombre, {}).get("cantidad", 0)),
            costo=_d(buckets.get(nombre, {}).get("costo")),
            venta=_d(buckets.get(nombre, {}).get("venta")),
            comision=_d(buckets.get(nombre, {}).get("comision")),
            margen=_d(buckets.get(nombre, {}).get("margen")),
        )
        for nombre in ordered
    ]


def _inspecciones_visitables(inspecciones: Iterable[Inspeccion]) -> list[Inspeccion]:
    return [
        inspeccion
        for inspeccion in inspecciones
        if inspeccion.estado_visita != "NO_APLICA"
    ]


def _resumen_agua(inspecciones: Iterable[Inspeccion]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    termo_intervalos: Counter[str] = Counter()
    for inspeccion in inspecciones:
        tipo = inspeccion.tipo_agua
        if tipo == "TERMO_ELECTRICO":
            counts["TERMO_ELECTRICO"] += 1
            if inspeccion.intervalo_mantencion == 6:
                termo_intervalos["6_MESES"] += 1
            elif inspeccion.intervalo_mantencion == 12:
                termo_intervalos["12_MESES"] += 1
            else:
                termo_intervalos["SIN_INTERVALO"] += 1
        elif tipo == "CALEFONT":
            counts["CALEFONT"] += 1
        elif tipo == "CALDERA_CENTRAL":
            counts["CALDERA_CENTRAL"] += 1
        else:
            counts["SIN_REVISAR"] += 1

    return {
        "TERMO_ELECTRICO": counts["TERMO_ELECTRICO"],
        "TERMO_6_MESES": termo_intervalos["6_MESES"],
        "TERMO_12_MESES": termo_intervalos["12_MESES"],
        "TERMO_SIN_INTERVALO": termo_intervalos["SIN_INTERVALO"],
        "CALEFONT": counts["CALEFONT"],
        "CALDERA_CENTRAL": counts["CALDERA_CENTRAL"],
        "SIN_REVISAR": counts["SIN_REVISAR"],
    }


def _resumen_compras(presupuestos: Iterable[Presupuesto]) -> dict[str, Decimal]:
    codigos = {codigo: ZERO for codigo, _, _ in MATERIALES}
    for presupuesto in presupuestos:
        for partida in presupuesto.partidas:
            codigo = str(partida.get("codigo") or "")
            if codigo in codigos:
                codigos[codigo] += _d(partida.get("cantidad"))
    return codigos


def _vacantes(inspecciones: Iterable[Inspeccion]) -> list[Inspeccion]:
    return sorted(
        (
            inspeccion
            for inspeccion in inspecciones
            if inspeccion.es_vacante or inspeccion.estado_propiedad == "Vacante"
        ),
        key=lambda item: (
            item.prioridad or "Z",
            -item.score,
            item.propiedad_id,
        ),
    )


def _m2_texto(valor: Decimal | None, pendiente: bool = False) -> str:
    if valor is None or valor <= 0:
        return "35 m² ref." if pendiente else "s/d"
    if valor == valor.to_integral():
        base = f"{int(valor)} m²"
    else:
        base = f"{valor.normalize():f} m²"
    return f"{base} ref." if pendiente else base


def _dormitorios_texto(inspeccion: Inspeccion) -> str:
    if inspeccion.dormitorios is None and inspeccion.banos is None:
        return "s/d"
    dormitorios = "s/d" if inspeccion.dormitorios is None else str(inspeccion.dormitorios)
    banos = "s/d" if inspeccion.banos is None else str(inspeccion.banos)
    return f"{dormitorios}D/{banos}B"


def _porcentaje(parte: Decimal | int, total: Decimal | int) -> Decimal:
    total_d = _d(total)
    if total_d == 0:
        return ZERO
    return (_d(parte) / total_d * 100).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)


def _tabla(
    headers: Sequence[str],
    rows: Sequence[Sequence[str]],
    aligns: Sequence[str] | None = None,
) -> str:
    align_values = list(aligns or ["left"] * len(headers))
    widths = [len(header) for header in headers]
    for row in rows:
        for index, cell in enumerate(row):
            widths[index] = max(widths[index], len(cell))

    def render(row: Sequence[str]) -> str:
        cells = []
        for index, cell in enumerate(row):
            if align_values[index] == "right":
                cells.append(cell.rjust(widths[index]))
            else:
                cells.append(cell.ljust(widths[index]))
        return " | ".join(cells).rstrip()

    separator = "-+-".join("-" * width for width in widths)
    return "\n".join([render(headers), separator, *(render(row) for row in rows)])


def _render_console(
    db_path: Path,
    routes_path: Path,
    inspecciones: Sequence[Inspeccion],
    presupuestos: Sequence[Presupuesto],
    rutas: Sequence[Ruta],
    generated_at: datetime,
) -> str:
    total_inspecciones = len(inspecciones)
    unidades_visitables = _inspecciones_visitables(inspecciones)
    estados = Counter(inspeccion.estado_visita for inspeccion in inspecciones)
    estados_extra = sorted(set(estados) - set(ESTADOS_INSPECCION))
    agua = _resumen_agua(unidades_visitables)
    financiero = _resumen_financiero(presupuestos)
    compras = _resumen_compras(presupuestos)
    vacantes = _vacantes(inspecciones)

    total_costo = sum((presupuesto.costo for presupuesto in presupuestos), ZERO)
    total_venta = sum((presupuesto.total for presupuesto in presupuestos), ZERO)
    total_comision = sum((presupuesto.comision for presupuesto in presupuestos), ZERO)
    total_margen = sum((presupuesto.margen for presupuesto in presupuestos), ZERO)
    pendientes = sum(
        1 for presupuesto in presupuestos if presupuesto.estado_medicion == "PENDIENTE_MEDICION"
    )

    lines = [
        "=" * 108,
        " DEPAFIX · TABLERO OPERATIVO TERRENO",
        f" Santiago Centro · {total_inspecciones} propiedades · {len(vacantes)} vacantes Ready-to-Rent",
        f" BD: {db_path} (solo lectura)",
        f" Rutas: {routes_path}",
        f" Generado: {generated_at.strftime('%Y-%m-%d %H:%M:%S %Z')}",
        "=" * 108,
        "",
        "[1] AVANCE DE INSPECCIONES",
        _tabla(
            ("Estado", "Cantidad", "%"),
            [
                (
                    estado,
                    str(estados[estado]),
                    f"{_porcentaje(estados[estado], total_inspecciones):.1f}%",
                )
                for estado in (*ESTADOS_INSPECCION, *estados_extra)
            ],
            ("left", "right", "right"),
        ),
        "",
        f"Total registros: {total_inspecciones}",
        "",
        "[2] AGUA CALIENTE",
        _tabla(
            ("Categoría", "Cantidad"),
            [
                ("TERMO_ELECTRICO", str(agua["TERMO_ELECTRICO"])),
                ("  · 6 meses", str(agua["TERMO_6_MESES"])),
                ("  · 12 meses", str(agua["TERMO_12_MESES"])),
                ("  · sin intervalo", str(agua["TERMO_SIN_INTERVALO"])),
                ("CALEFONT", str(agua["CALEFONT"])),
                ("CALDERA_CENTRAL", str(agua["CALDERA_CENTRAL"])),
                ("SIN_REVISAR", str(agua["SIN_REVISAR"])),
                ("TOTAL", str(len(unidades_visitables))),
            ],
            ("left", "right"),
        ),
        "Nota: SIN_INFORMACION se reporta como SIN_REVISAR. "
        f"Base: {len(unidades_visitables)} unidades visitables; "
        f"{total_inspecciones - len(unidades_visitables)} registro(s) NO_APLICA excluido(s).",
        "",
        "[3] PRESUPUESTOS POR ESTADO / SINCRONIZACIÓN",
        _tabla(
            (
                "Estado",
                "N°",
                "Costo mayorista",
                "Venta neta",
                "Comisión 10% corredor",
                "Margen DepaFix",
            ),
            [
                (
                    bucket.nombre,
                    str(bucket.cantidad),
                    formato_clp(bucket.costo),
                    formato_clp(bucket.venta),
                    formato_clp(bucket.comision),
                    formato_clp(bucket.margen),
                )
                for bucket in financiero
            ]
            + [
                (
                    "TOTAL",
                    str(len(presupuestos)),
                    formato_clp(total_costo),
                    formato_clp(total_venta),
                    formato_clp(total_comision),
                    formato_clp(total_margen),
                )
            ],
            ("left", "right", "right", "right", "right", "right"),
        ),
        f"Margen DepaFix: {_porcentaje(total_margen, total_venta):.1f}% · "
        f"Medición pendiente: {pendientes} presupuestos",
        "",
        "[4] CONSOLIDADO DE COMPRAS MAYORISTAS",
        _tabla(
            ("Insumo", "Unidad", "Cantidad"),
            [
                (
                    nombre,
                    unidad,
                    f"{compras[codigo].normalize():f}",
                )
                for codigo, nombre, unidad in MATERIALES
            ],
            ("left", "left", "right"),
        ),
        f"Costo mayorista estimado del paquete: {formato_clp(total_costo)}",
        "",
        "[5] RUTAS DE TERRENO",
        _tabla(
            ("Segmento", "Bloque", "Paradas", "Unidades", "Trayecto"),
            [
                (
                    ruta.segmento,
                    ruta.bloque,
                    str(ruta.paradas),
                    str(ruta.unidades),
                    f"{ruta.primera_parada} → {ruta.ultima_parada}",
                )
                for ruta in rutas
            ],
            ("left", "left", "right", "right", "left"),
        ),
    ]
    return "\n".join(lines)


def _e(value: object) -> str:
    return html.escape(str(value), quote=True)


def _kpi(label: str, value: str, note: str = "", accent: str = "") -> str:
    accent_class = f" {accent}" if accent else ""
    note_html = f'<p class="kpi-note">{_e(note)}</p>' if note else ""
    return (
        f'<article class="kpi{accent_class}">'
        f'<span class="kpi-label">{_e(label)}</span>'
        f'<strong class="kpi-value">{_e(value)}</strong>'
        f"{note_html}</article>"
    )


def _badge(estado_medicion: str) -> str:
    if estado_medicion == "PENDIENTE_MEDICION":
        return '<span class="badge badge-warn">PENDIENTE_MEDICION</span>'
    if estado_medicion == "MEDIDO":
        return '<span class="badge badge-ok">MEDIDO</span>'
    return f'<span class="badge">{_e(estado_medicion or "SIN_ESTADO")}</span>'


def _render_html(
    db_path: Path,
    inspecciones: Sequence[Inspeccion],
    presupuestos: Sequence[Presupuesto],
    rutas: Sequence[Ruta],
    generated_at: datetime,
) -> str:
    latest = {presupuesto.inspeccion_id: presupuesto for presupuesto in presupuestos}
    vacantes = _vacantes(inspecciones)
    financiero = _resumen_financiero(presupuestos)
    compras = _resumen_compras(presupuestos)
    unidades_visitables = _inspecciones_visitables(inspecciones)
    agua = _resumen_agua(unidades_visitables)

    total_costo = sum((presupuesto.costo for presupuesto in presupuestos), ZERO)
    total_venta = sum((presupuesto.total for presupuesto in presupuestos), ZERO)
    total_comision = sum((presupuesto.comision for presupuesto in presupuestos), ZERO)
    total_margen = sum((presupuesto.margen for presupuesto in presupuestos), ZERO)
    pendientes = sum(
        1 for presupuesto in presupuestos if presupuesto.estado_medicion == "PENDIENTE_MEDICION"
    )
    margen_bruto = total_venta - total_costo
    margen_pct = _porcentaje(total_margen, total_venta)
    roi_bruto = _porcentaje(margen_bruto, total_costo)
    roi_depafix = _porcentaje(total_margen, total_costo)
    uplift_mensual = ROI_UPLIFT_MENSUAL * len(vacantes)
    uplift_anual = uplift_mensual * 12
    payback_venta = (
        (total_venta / uplift_mensual).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
        if uplift_mensual
        else ZERO
    )
    payback_costo = (
        (total_costo / uplift_mensual).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
        if uplift_mensual
        else ZERO
    )

    rows: list[str] = []
    for inspeccion in vacantes:
        presupuesto = latest.get(inspeccion.id)
        if presupuesto is None:
            m2 = _m2_texto(inspeccion.superficie_m2)
            medicion = "SIN_PRESUPUESTO"
            venta = comision = margen = ZERO
            ruta = inspeccion.segmento_ruta or "s/d"
        else:
            pendiente = presupuesto.estado_medicion == "PENDIENTE_MEDICION"
            m2 = _m2_texto(
                inspeccion.superficie_m2 or presupuesto.m2_spc,
                pendiente=pendiente,
            )
            medicion = presupuesto.estado_medicion
            venta = presupuesto.total
            comision = presupuesto.comision
            margen = presupuesto.margen
            ruta = inspeccion.segmento_ruta or "s/d"
        rows.append(
            "<tr>"
            f'<td class="mono">{_e(inspeccion.propiedad_id)}</td>'
            f"<td>{_e(inspeccion.direccion)}</td>"
            f'<td class="num">{_e(m2)}</td>'
            f"<td>{_e(_dormitorios_texto(inspeccion))}</td>"
            f'<td class="center"><span class="priority">{_e(inspeccion.prioridad or "s/d")}</span></td>'
            f'<td class="center">{_e(ruta)}</td>'
            f"<td>{_badge(medicion)}</td>"
            f'<td class="num">{_e(formato_clp(venta))}</td>'
            f'<td class="num">{_e(formato_clp(comision))}</td>'
            f'<td class="num strong">{_e(formato_clp(margen))}</td>'
            "</tr>"
        )

    financial_rows = "".join(
        "<tr>"
        f"<td>{_e(bucket.nombre)}</td>"
        f'<td class="num">{bucket.cantidad}</td>'
        f'<td class="num">{_e(formato_clp(bucket.costo))}</td>'
        f'<td class="num">{_e(formato_clp(bucket.venta))}</td>'
        f'<td class="num">{_e(formato_clp(bucket.comision))}</td>'
        f'<td class="num strong">{_e(formato_clp(bucket.margen))}</td>'
        "</tr>"
        for bucket in financiero
    )

    material_rows = "".join(
        "<tr>"
        f"<td>{_e(nombre)}</td>"
        f'<td class="center">{_e(unidad)}</td>'
        f'<td class="num strong">{_e(f"{compras[codigo].normalize():f}")}</td>'
        "</tr>"
        for codigo, nombre, unidad in MATERIALES
    )

    route_cards = "".join(
        '<article class="route-card">'
        '<div class="route-head">'
        f'<span class="route-code">{_e(ruta.segmento)}</span>'
        f'<span class="route-block">{_e(ruta.bloque)}</span>'
        "</div>"
        '<div class="route-metrics">'
        f"<span><strong>{ruta.paradas}</strong> paradas</span>"
        f"<span><strong>{ruta.unidades}</strong> unidades</span>"
        f"<span><strong>{ruta.waypoints}</strong> waypoints</span>"
        "</div>"
        f'<p class="route-path">{_e(ruta.primera_parada)} → {_e(ruta.ultima_parada)}</p>'
        f'<a class="btn" href="{_e(ruta.url)}" target="_blank" '
        'rel="noopener noreferrer">Abrir ruta en Google Maps</a>'
        "</article>"
        for ruta in rutas
    )

    kpis = "".join(
        [
            _kpi("Venta neta", formato_clp(total_venta), f"{len(vacantes)} vacantes", "accent"),
            _kpi("Comisión corredor", formato_clp(total_comision), "10% de la venta neta"),
            _kpi("Margen DepaFix", formato_clp(total_margen), f"{margen_pct:.1f}% de la venta"),
            _kpi("Costo mayorista", formato_clp(total_costo), "CAPEX del paquete"),
            _kpi("ROI bruto", f"{roi_bruto:.1f}%", "Margen bruto / costo"),
            _kpi(
                "Medición pendiente",
                str(pendientes),
                "Presupuestos por confirmar",
                "accent-warm",
            ),
        ]
    )

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="dark light">
<title>DepaFix · Propuesta Ejecutiva Corredor</title>
<style>
{CSS}
</style>
</head>
<body>
<div class="page">
<header class="hero">
  <div>
    <p class="eyebrow">DEPAFIX · OPERACIÓN TERRENO</p>
    <h1>Propuesta Ejecutiva<br><span>Corredor Santiago Centro</span></h1>
    <p class="lead">Paquete Ready-to-Rent de {len(vacantes)} vacantes con mejora de piso SPC,
    iluminación LED y terminaciones. Cifras netas en CLP, calculadas con Decimal.</p>
  </div>
  <div class="hero-side">
    <span class="stamp">DOSSIER CONFIDENCIAL</span>
    <p class="hero-date">{generated_at.strftime('%d-%m-%Y')}</p>
    <p class="hero-meta">{len(inspecciones)} propiedades · {len(rutas)} rutas · {len(vacantes)} vacantes</p>
    <p class="hero-source">Fuente: {_e(db_path.name)}</p>
  </div>
</header>

<nav class="topnav no-print">
  <a href="#resumen">Resumen</a>
  <a href="#vacantes">Vacantes</a>
  <a href="#retorno">Retorno</a>
  <a href="#rutas">Rutas</a>
</nav>

<section id="resumen">
  <div class="section-head">
    <div>
      <p class="eyebrow">01 · RESUMEN EJECUTIVO</p>
      <h2>Un paquete listo para competir</h2>
    </div>
    <p class="section-note">Venta neta, comisión y margen consolidados de los presupuestos
    vigentes. {pendientes} vacantes requieren confirmación de metraje.</p>
  </div>
  <div class="kpi-grid">{kpis}</div>
  <div class="panel-grid">
    <article class="panel">
      <h3>Oferta consolidada</h3>
      <p>Mejorar el estándar de las unidades antes de publicar acorta el tiempo de vacancia:
      piso SPC resistente al agua, plafones LED, módulos eléctricos, soporte TV, mantención
      de termo y sellado antihongo.</p>
      <p class="muted">El paquete incluye {agua["TERMO_ELECTRICO"]} termos detectados;
      {agua["SIN_REVISAR"]} de {len(unidades_visitables)} unidades visitables aún están
      sin revisión de agua caliente. El registro administrativo NO_APLICA se excluye
      de este conteo.</p>
    </article>
    <article class="panel">
      <h3>Lectura comercial</h3>
      <p>El corredor recibe una comisión de {formato_clp(total_comision)} sobre una venta neta
      de {formato_clp(total_venta)}. El margen DepaFix asciende a {formato_clp(total_margen)}
      ({margen_pct:.1f}%).</p>
      <p class="muted">Los montos no incluyen IVA ni gastos no especificados. La medición real
      se confirma antes de cerrar la propuesta definitiva.</p>
    </article>
  </div>
</section>

<section id="vacantes">
  <div class="section-head">
    <div>
      <p class="eyebrow">02 · VACANTES PRIORITARIAS</p>
      <h2>{len(vacantes)} unidades Ready-to-Rent</h2>
    </div>
    <p class="section-note">Ordenadas por prioridad y score. Las filas con
    <span class="badge badge-warn">PENDIENTE_MEDICION</span> usan 35 m² referenciales.</p>
  </div>
  <div class="table-wrap">
    <table class="data-table">
      <thead>
        <tr>
          <th>ID</th><th>Dirección</th><th class="num">m²</th><th>Dorm/Baños</th>
          <th class="center">Prioridad</th><th class="center">Ruta</th><th>Medición</th>
          <th class="num">Venta neta</th><th class="num">Comisión</th><th class="num">Margen</th>
        </tr>
      </thead>
      <tbody>{''.join(rows)}</tbody>
      <tfoot>
        <tr>
          <td colspan="7"><strong>TOTAL PAQUETE</strong></td>
          <td class="num"><strong>{_e(formato_clp(total_venta))}</strong></td>
          <td class="num"><strong>{_e(formato_clp(total_comision))}</strong></td>
          <td class="num"><strong>{_e(formato_clp(total_margen))}</strong></td>
        </tr>
      </tfoot>
    </table>
  </div>
  <div class="summary-strip">
    <span><strong>{len(vacantes)}</strong> vacantes</span>
    <span><strong>{_m2_total(compras)}</strong> m² SPC</span>
    <span><strong>{pendientes}</strong> mediciones pendientes</span>
    <span><strong>{formato_clp(total_costo)}</strong> compra mayorista</span>
  </div>
</section>

<section id="retorno">
  <div class="section-head">
    <div>
      <p class="eyebrow">03 · ARGUMENTO DE RETORNO</p>
      <h2>Invertir antes de publicar<br>para arrendar mejor</h2>
    </div>
    <p class="section-note">ROI del paquete sobre costo mayorista y payback estimado para el
    propietario. La mejora se traduce en fotos más competitivas y menor fricción comercial.</p>
  </div>
  <div class="roi-grid">
    <article class="roi-card">
      <span>ROI bruto del paquete</span>
      <strong>{roi_bruto:.1f}%</strong>
      <p>Margen bruto de {formato_clp(margen_bruto)} sobre una compra mayorista de
      {formato_clp(total_costo)}.</p>
    </article>
    <article class="roi-card">
      <span>ROI neto DepaFix</span>
      <strong>{roi_depafix:.1f}%</strong>
      <p>Margen DepaFix de {formato_clp(total_margen)} después de la comisión del corredor.</p>
    </article>
    <article class="roi-card">
      <span>Payback sobre venta neta</span>
      <strong>{payback_venta:.1f} meses</strong>
      <p>Con {formato_clp(uplift_mensual)} de uplift mensual agregado para las
      {len(vacantes)} unidades.</p>
    </article>
    <article class="roi-card">
      <span>Payback sobre costo</span>
      <strong>{payback_costo:.1f} meses</strong>
      <p>Recuperación del CAPEX mayorista con el mismo supuesto de renta.</p>
    </article>
  </div>
  <p class="assumption">{_e(ROI_UPLIFT_TEXTO)} El uplift anual agregado sería
  {formato_clp(uplift_anual)}. No es una garantía de renta; depende de demanda, tasación y
  condiciones del inmueble.</p>
  <div class="table-wrap">
    <table class="compare-table">
      <thead><tr><th>Antes</th><th>Después</th><th>Impacto técnico</th></tr></thead>
      <tbody>
        <tr><td>Alfombra percudida o piso desgastado</td><td>Piso SPC 4-5 mm + manta</td><td>Superficie lavable, instalación rápida y mejor percepción en fotografías.</td></tr>
        <tr><td>Iluminación antigua y alto consumo</td><td>Plafones LED 18W/24W</td><td>Mayor luminosidad, menor consumo y mejor presentación del aviso.</td></tr>
        <tr><td>Enchufes sueltos o fuera de norma</td><td>Módulos Bticino/Legrand</td><td>Reduce riesgo eléctrico y mejora la percepción de seguridad.</td></tr>
        <tr><td>Termo sin mantención</td><td>Ánodo + purga de sarro</td><td>Evita fallas, pérdida de eficiencia y sobreconsumo.</td></tr>
        <tr><td>Filtraciones en baño o cocina</td><td>Sellado antihongo perimetral</td><td>Protege unidades inferiores y reduce multas de administración.</td></tr>
      </tbody>
    </table>
  </div>
  <div class="fin-panel">
    <h3>Resumen financiero por estado / sincronización</h3>
    <div class="table-wrap">
      <table class="data-table compact">
        <thead><tr><th>Estado</th><th class="num">N°</th><th class="num">Costo mayorista</th><th class="num">Venta neta</th><th class="num">Comisión 10% corredor</th><th class="num">Margen</th></tr></thead>
        <tbody>{financial_rows}</tbody>
        <tfoot><tr><td><strong>TOTAL</strong></td><td class="num"><strong>{len(presupuestos)}</strong></td><td class="num"><strong>{_e(formato_clp(total_costo))}</strong></td><td class="num"><strong>{_e(formato_clp(total_venta))}</strong></td><td class="num"><strong>{_e(formato_clp(total_comision))}</strong></td><td class="num"><strong>{_e(formato_clp(total_margen))}</strong></td></tr></tfoot>
      </table>
    </div>
  </div>
</section>

<section id="rutas">
  <div class="section-head">
    <div>
      <p class="eyebrow">04 · OPERACIÓN EN TERRENO</p>
      <h2>Cuatro rutas, una ejecución</h2>
    </div>
    <p class="section-note">Enlaces directos a Google Maps para inspección y validación de las
    unidades. Rutas optimizadas por cercanía.</p>
  </div>
  <div class="route-grid">{route_cards}</div>
</section>

<section id="compras">
  <div class="section-head">
    <div>
      <p class="eyebrow">05 · COMPRA MAYORISTA</p>
      <h2>Consolidado de materiales</h2>
    </div>
    <p class="section-note">Cantidades agregadas de los presupuestos vigentes. Incluye metraje
    referencial de las unidades pendientes de medición.</p>
  </div>
  <div class="table-wrap">
    <table class="data-table compact">
      <thead><tr><th>Insumo</th><th class="center">Unidad</th><th class="num">Cantidad</th></tr></thead>
      <tbody>{material_rows}</tbody>
    </table>
  </div>
</section>

<footer>
  <p><strong>DepaFix · Operación Terreno Santiago Centro</strong></p>
  <p>Documento generado automáticamente desde la base operativa y las rutas de Google Maps.
  Sin datos personales de propietarios, arrendatarios o contactos.</p>
  <p class="muted">Montos netos en CLP. La comisión del corredor corresponde al 10% de la venta
  neta. Las mediciones pendientes deben confirmarse antes del cierre definitivo.</p>
</footer>
</div>
</body>
</html>
"""


def _m2_total(compras: dict[str, Decimal]) -> str:
    value = compras.get("SPC-001", ZERO)
    if value == value.to_integral():
        return str(int(value))
    return f"{value.normalize():f}"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Muestra el tablero operativo de terreno y exporta el dossier ejecutivo "
            "del corredor."
        )
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB_PATH,
        help="Ruta de la base SQLite operativa (se abre en modo solo lectura).",
    )
    parser.add_argument(
        "--routes",
        type=Path,
        default=DEFAULT_ROUTES_JSON,
        help="Ruta del JSON de rutas de Google Maps.",
    )
    parser.add_argument(
        "--export-html",
        type=Path,
        metavar="RUTA",
        help="Exporta el dossier ejecutivo HTML autocontenido.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    db_path = args.db.expanduser()
    routes_path = args.routes.expanduser()
    if not db_path.exists():
        print(f"ERROR: no existe la base de datos {db_path}", file=sys.stderr)
        return 1
    if not routes_path.exists():
        print(f"ERROR: no existe el archivo de rutas {routes_path}", file=sys.stderr)
        return 1

    try:
        with _conectar_ro(db_path) as connection:
            inspecciones = _cargar_inspecciones(connection)
            todos_los_presupuestos = _cargar_presupuestos(connection)
        presupuestos = _presupuestos_actuales(todos_los_presupuestos)
        rutas = _cargar_rutas(routes_path)
        generated_at = datetime.now().astimezone()

        print(
            _render_console(
                db_path,
                routes_path,
                inspecciones,
                presupuestos,
                rutas,
                generated_at,
            )
        )

        if args.export_html:
            output_path = args.export_html.expanduser()
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(
                _render_html(
                    db_path,
                    inspecciones,
                    presupuestos,
                    rutas,
                    generated_at,
                ),
                encoding="utf-8",
            )
            print(f"\nDossier HTML: {output_path}")
        return 0
    except (sqlite3.Error, OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


CSS = """
:root {
  --bg: #080d16;
  --panel: #101a2b;
  --panel-2: #152238;
  --line: #263650;
  --text: #e8eef7;
  --muted: #94a6bf;
  --gold: #d8b26a;
  --teal: #55c7b7;
  --warm: #f0ad68;
  --ok: #73d6a4;
  --danger: #ff8b8b;
}
* { box-sizing: border-box; }
html { scroll-behavior: smooth; }
body {
  margin: 0;
  background:
    radial-gradient(circle at 12% 0%, rgba(85, 199, 183, 0.13), transparent 32rem),
    radial-gradient(circle at 88% 4%, rgba(216, 178, 106, 0.11), transparent 30rem),
    var(--bg);
  color: var(--text);
  font-family: "Segoe UI", "Helvetica Neue", Arial, sans-serif;
  font-size: 15px;
  line-height: 1.55;
}
a { color: var(--teal); }
.page { width: min(1180px, calc(100% - 40px)); margin: 0 auto; padding: 28px 0 44px; }
.hero {
  display: grid;
  grid-template-columns: 1.6fr 0.8fr;
  gap: 28px;
  padding: 38px 40px;
  border: 1px solid var(--line);
  border-radius: 22px;
  background:
    linear-gradient(135deg, rgba(21, 34, 56, 0.98), rgba(10, 17, 30, 0.96)),
    var(--panel);
  box-shadow: 0 22px 70px rgba(0, 0, 0, 0.38);
}
.eyebrow {
  margin: 0 0 10px;
  color: var(--gold);
  font-size: 0.72rem;
  font-weight: 800;
  letter-spacing: 0.2em;
}
h1 { margin: 0; font-size: clamp(2rem, 5vw, 3.7rem); line-height: 1.04; letter-spacing: -0.035em; }
h1 span { color: var(--gold); }
h2 { margin: 0; font-size: clamp(1.55rem, 3vw, 2.4rem); line-height: 1.12; letter-spacing: -0.02em; }
h3 { margin: 0 0 10px; font-size: 1.02rem; color: var(--gold); }
.lead { max-width: 58ch; margin: 18px 0 0; color: #b9c8dc; font-size: 1.02rem; }
.hero-side {
  display: flex;
  flex-direction: column;
  justify-content: flex-end;
  align-items: flex-start;
  gap: 8px;
  padding: 22px;
  border: 1px solid var(--line);
  border-radius: 16px;
  background: rgba(8, 13, 22, 0.46);
}
.stamp {
  display: inline-block;
  padding: 6px 9px;
  border: 1px solid rgba(216, 178, 106, 0.55);
  border-radius: 999px;
  color: var(--gold);
  font-size: 0.65rem;
  font-weight: 800;
  letter-spacing: 0.16em;
}
.hero-date { margin: 10px 0 0; font-size: 1.55rem; font-weight: 800; }
.hero-meta, .hero-source, .muted { color: var(--muted); }
.hero-meta { margin: 0; font-size: 0.86rem; }
.hero-source { margin: 0; font-size: 0.72rem; overflow-wrap: anywhere; }
.topnav {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin: 18px 0 32px;
  padding: 8px;
  border: 1px solid var(--line);
  border-radius: 999px;
  background: rgba(16, 26, 43, 0.8);
}
.topnav a {
  padding: 7px 14px;
  border-radius: 999px;
  color: var(--muted);
  font-size: 0.78rem;
  font-weight: 700;
  text-decoration: none;
}
.topnav a:hover { background: var(--panel-2); color: var(--text); }
section { margin: 42px 0 0; scroll-margin-top: 18px; }
.section-head {
  display: flex;
  justify-content: space-between;
  align-items: end;
  gap: 28px;
  margin-bottom: 18px;
}
.section-note { max-width: 42ch; margin: 0; color: var(--muted); font-size: 0.86rem; }
.kpi-grid { display: grid; grid-template-columns: repeat(6, 1fr); gap: 10px; }
.kpi {
  min-height: 118px;
  padding: 16px 15px;
  border: 1px solid var(--line);
  border-radius: 14px;
  background: linear-gradient(180deg, rgba(21, 34, 56, 0.95), rgba(16, 26, 43, 0.92));
}
.kpi.accent { border-color: rgba(85, 199, 183, 0.42); }
.kpi.accent-warm { border-color: rgba(240, 173, 104, 0.45); }
.kpi-label { display: block; color: var(--muted); font-size: 0.67rem; font-weight: 800; letter-spacing: 0.08em; text-transform: uppercase; }
.kpi-value { display: block; margin-top: 10px; font-size: 1.24rem; line-height: 1.12; }
.kpi-note { margin: 8px 0 0; color: var(--muted); font-size: 0.68rem; }
.panel-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-top: 12px; }
.panel, .fin-panel {
  padding: 20px;
  border: 1px solid var(--line);
  border-radius: 15px;
  background: rgba(16, 26, 43, 0.86);
}
.panel p { margin: 0 0 10px; }
.panel p:last-child { margin-bottom: 0; }
.table-wrap { overflow-x: auto; border: 1px solid var(--line); border-radius: 15px; background: rgba(16, 26, 43, 0.9); }
table { width: 100%; border-collapse: collapse; }
th, td { padding: 11px 12px; border-bottom: 1px solid rgba(38, 54, 80, 0.78); text-align: left; vertical-align: top; }
th { color: var(--muted); font-size: 0.67rem; letter-spacing: 0.06em; text-transform: uppercase; white-space: nowrap; }
td { font-size: 0.82rem; }
tbody tr:hover { background: rgba(85, 199, 183, 0.05); }
tfoot td { border-top: 1px solid var(--gold); border-bottom: 0; background: rgba(216, 178, 106, 0.06); }
.num { text-align: right; white-space: nowrap; }
.center { text-align: center; }
.mono { font-family: "SFMono-Regular", Consolas, "Liberation Mono", monospace; font-size: 0.76rem; }
.strong { color: #fff; font-weight: 800; }
.badge {
  display: inline-block;
  padding: 3px 7px;
  border: 1px solid var(--line);
  border-radius: 999px;
  color: var(--muted);
  font-size: 0.62rem;
  font-weight: 800;
  letter-spacing: 0.04em;
  white-space: nowrap;
}
.badge-warn { border-color: rgba(240, 173, 104, 0.6); color: var(--warm); background: rgba(240, 173, 104, 0.08); }
.badge-ok { border-color: rgba(115, 214, 164, 0.5); color: var(--ok); background: rgba(115, 214, 164, 0.07); }
.priority { display: inline-grid; place-items: center; width: 25px; height: 25px; border: 1px solid var(--gold); border-radius: 50%; color: var(--gold); font-weight: 800; font-size: 0.72rem; }
.summary-strip { display: flex; flex-wrap: wrap; gap: 10px 24px; margin-top: 12px; padding: 14px 16px; border: 1px solid var(--line); border-radius: 13px; color: var(--muted); font-size: 0.8rem; }
.summary-strip strong { color: var(--text); }
.roi-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; }
.roi-card { padding: 18px; border: 1px solid var(--line); border-radius: 14px; background: linear-gradient(150deg, rgba(21, 34, 56, 0.98), rgba(16, 26, 43, 0.9)); }
.roi-card span { display: block; color: var(--muted); font-size: 0.68rem; font-weight: 800; letter-spacing: 0.06em; text-transform: uppercase; }
.roi-card strong { display: block; margin: 8px 0 7px; color: var(--gold); font-size: 1.75rem; line-height: 1; }
.roi-card p { margin: 0; color: var(--muted); font-size: 0.78rem; }
.assumption { margin: 12px 0; padding: 13px 15px; border-left: 3px solid var(--gold); background: rgba(216, 178, 106, 0.07); color: #cbd8e8; font-size: 0.8rem; }
.compare-table th, .compare-table td { font-size: 0.8rem; }
.fin-panel { margin-top: 14px; }
.compact th, .compact td { padding: 9px 11px; }
.route-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; }
.route-card { display: flex; flex-direction: column; padding: 18px; border: 1px solid var(--line); border-radius: 14px; background: linear-gradient(160deg, rgba(21, 34, 56, 0.97), rgba(10, 17, 30, 0.94)); }
.route-head { display: flex; justify-content: space-between; align-items: center; gap: 10px; }
.route-code { color: var(--gold); font-size: 1.7rem; font-weight: 900; letter-spacing: -0.04em; }
.route-block { color: var(--muted); font-size: 0.68rem; font-weight: 800; text-transform: uppercase; }
.route-metrics { display: flex; flex-wrap: wrap; gap: 4px 10px; margin: 12px 0 8px; color: var(--muted); font-size: 0.7rem; }
.route-metrics strong { color: var(--text); }
.route-path { flex: 1; margin: 0 0 16px; color: #c4d2e3; font-size: 0.76rem; }
.btn { display: inline-flex; justify-content: center; align-items: center; min-height: 36px; padding: 8px 12px; border: 1px solid rgba(85, 199, 183, 0.55); border-radius: 9px; background: rgba(85, 199, 183, 0.1); color: #9be9de; font-size: 0.72rem; font-weight: 800; text-decoration: none; }
.btn:hover { background: rgba(85, 199, 183, 0.2); }
footer { margin-top: 42px; padding-top: 18px; border-top: 1px solid var(--line); color: #c6d3e4; font-size: 0.78rem; }
footer p { margin: 4px 0; }
@media (max-width: 980px) {
  .hero { grid-template-columns: 1fr; }
  .kpi-grid { grid-template-columns: repeat(3, 1fr); }
  .roi-grid, .route-grid { grid-template-columns: repeat(2, 1fr); }
}
@media (max-width: 620px) {
  .page { width: min(100% - 22px, 1180px); padding-top: 14px; }
  .hero { padding: 24px 20px; }
  .section-head { display: block; }
  .section-note { margin-top: 8px; }
  .kpi-grid, .panel-grid, .roi-grid, .route-grid { grid-template-columns: 1fr; }
  .kpi { min-height: 0; }
}
@media print {
  @page { size: A4 portrait; margin: 12mm; }
  :root {
    --bg: #ffffff;
    --panel: #ffffff;
    --panel-2: #f5f7fa;
    --line: #c9d2de;
    --text: #111820;
    --muted: #546273;
    --gold: #765515;
    --teal: #0c675d;
    --warm: #8a4d14;
    --ok: #17663f;
  }
  body { background: #fff; color: #111820; font-size: 10.5pt; }
  .page { width: 100%; padding: 0; }
  .hero { padding: 20px; border-radius: 10px; box-shadow: none; background: #fff; }
  .hero-side, .panel, .fin-panel, .kpi, .roi-card, .route-card, .table-wrap { background: #fff; box-shadow: none; }
  .topnav, .no-print { display: none !important; }
  section { margin-top: 24px; }
  .kpi-grid { grid-template-columns: repeat(3, 1fr); }
  .roi-grid, .route-grid { grid-template-columns: repeat(2, 1fr); }
  .kpi, .roi-card, .route-card, .panel, .fin-panel, tr { break-inside: avoid; page-break-inside: avoid; }
  .table-wrap { overflow: visible; }
  table { font-size: 8.7pt; }
  th, td { padding: 6px 7px; }
  a { color: #111820; text-decoration: none; }
  .btn { background: #fff; color: #111820; border: 1px solid #7d8b9c; }
  .badge { border-color: #8b98a8; color: #333; background: #fff; }
  footer { color: #333; }
  .muted, .section-note, .kpi-note { color: #546273; }
}
"""


if __name__ == "__main__":
    sys.exit(main())
