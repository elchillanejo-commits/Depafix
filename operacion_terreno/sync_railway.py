from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import DEFAULT_DB_PATH
from .db import PresupuestoObra, init_db

DEFAULT_ENDPOINT = (
    "https://depafix-presupuestos-production.up.railway.app/api/v1/cotizaciones/"
)
ESTADO_APROBADO = "APROBADO"
SYNC_OK = "SINCRONIZADO"
SYNC_ERROR = "ERROR"
USER_AGENT = "DepaFix-Operations/1.0"


class SyncError(RuntimeError):
    pass


def _d(value: object) -> Decimal:
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise SyncError(f"Valor monetario inválido: {value!r}") from exc


def _item_codigo(partida: dict[str, Any], index: int) -> str:
    codigo = str(partida.get("codigo") or "").strip()
    if codigo:
        return codigo
    desc = str(partida.get("desc") or "").strip()
    if " - " in desc:
        return desc.split(" - ", 1)[0].strip()
    return f"PARTIDA-{index:02d}"


def construir_payload(presupuesto: PresupuestoObra) -> dict[str, Any]:
    if presupuesto.payload_json:
        payload = dict(presupuesto.payload_json)
    else:
        inspeccion = presupuesto.inspeccion
        items: list[dict[str, Any]] = []
        for index, partida in enumerate(presupuesto.partidas or [], start=1):
            precio = partida.get("precio_unitario", partida.get("precio"))
            cantidad = partida.get("cantidad", 1)
            items.append(
                {
                    "codigo": _item_codigo(partida, index),
                    "desc": str(partida.get("desc") or ""),
                    "cantidad": float(_d(cantidad)),
                    "precio": float(_d(precio)),
                }
            )
        payload = {
            "direccion": inspeccion.direccion,
            "comuna": inspeccion.comuna or "Santiago",
            "items": items,
            "total_neto": float(_d(presupuesto.total or presupuesto.neto)),
        }
    validar_payload(payload)
    return payload


def validar_payload(payload: dict[str, Any]) -> None:
    direccion = str(payload.get("direccion") or "").strip()
    if len(direccion) < 5:
        raise SyncError("El payload no tiene una dirección válida.")
    items = payload.get("items")
    if not isinstance(items, list) or not items:
        raise SyncError("El payload no tiene ítems.")
    total = _d(payload.get("total_neto"))
    if total <= 0:
        raise SyncError("El payload no tiene total_neto positivo.")
    suma = Decimal("0")
    for item in items:
        if not isinstance(item, dict):
            raise SyncError("Ítem de payload inválido.")
        if not str(item.get("desc") or "").strip():
            raise SyncError("Ítem sin descripción.")
        precio = _d(item.get("precio"))
        cantidad = _d(item.get("cantidad", 1))
        if precio <= 0 or cantidad <= 0:
            raise SyncError("Ítem con precio o cantidad no positivos.")
        suma += precio * cantidad
    diferencia = abs(suma - total)
    if diferencia > Decimal("1"):
        raise SyncError(
            f"total_neto ({total}) no coincide con suma de ítems ({suma}); "
            f"diferencia {diferencia}."
        )


def _post_json(
    endpoint: str, payload: dict[str, Any], api_key: str | None, timeout: int
) -> tuple[int, dict[str, Any] | str]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": USER_AGENT,
    }
    if api_key:
        headers["X-API-Key"] = api_key
    request = urllib.request.Request(
        endpoint, data=body, headers=headers, method="POST"
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
            try:
                parsed: dict[str, Any] | str = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                parsed = raw
            return response.status, parsed
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        raise SyncError(f"HTTP {exc.code}: {raw[:1000]}") from exc
    except urllib.error.URLError as exc:
        raise SyncError(f"Error de conexión: {exc.reason}") from exc


def _extraer_uuid(response: dict[str, Any] | str) -> str | None:
    if not isinstance(response, dict):
        return None
    candidates: list[Any] = [response.get("uuid"), response.get("id")]
    data = response.get("data")
    if isinstance(data, dict):
        candidates.extend([data.get("uuid"), data.get("id")])
    for value in candidates:
        if value not in (None, ""):
            return str(value)
    return None


def _seleccionar(
    session: Session, ids: list[str] | None, force: bool
) -> list[PresupuestoObra]:
    query = select(PresupuestoObra)
    if ids:
        query = query.where(PresupuestoObra.propiedad_id.in_(ids))
    else:
        query = query.where(PresupuestoObra.estado == ESTADO_APROBADO)
    if not force:
        query = query.where(PresupuestoObra.sync_status != SYNC_OK)
    return list(session.scalars(query.order_by(PresupuestoObra.id.asc())))


def sincronizar(
    db_path: Path = DEFAULT_DB_PATH,
    endpoint: str = DEFAULT_ENDPOINT,
    api_key: str | None = None,
    ids: list[str] | None = None,
    force: bool = False,
    send: bool = False,
    timeout: int = 30,
) -> dict[str, int]:
    engine = init_db(f"sqlite:///{db_path}")
    stats = {"seleccionados": 0, "enviados": 0, "omitidos": 0, "errores": 0}

    with Session(engine) as session:
        presupuestos = _seleccionar(session, ids, force)
        stats["seleccionados"] = len(presupuestos)
        if not presupuestos:
            print("No hay presupuestos candidatos para sincronizar.")
            if not ids:
                print(
                    "Sugerencia: crea/aprueba un presupuesto o usa "
                    "--id <propiedad_id> en dry-run para revisar una simulación."
                )
            return stats

        for presupuesto in presupuestos:
            etiqueta = f"{presupuesto.propiedad_id} (id={presupuesto.id})"
            try:
                payload = construir_payload(presupuesto)
            except SyncError as exc:
                stats["errores"] += 1
                print(f"[ERROR] {etiqueta}: {exc}")
                if send:
                    presupuesto.sync_status = SYNC_ERROR
                    presupuesto.sync_error = str(exc)
                    session.commit()
                continue

            if not send:
                print(f"[DRY-RUN] {etiqueta} estado={presupuesto.estado}")
                print(json.dumps(payload, ensure_ascii=False, indent=2))
                continue

            if presupuesto.estado != ESTADO_APROBADO and not force:
                stats["omitidos"] += 1
                print(
                    f"[OMITIDO] {etiqueta}: estado={presupuesto.estado}; "
                    "usa --force solo para pruebas/mock."
                )
                continue
            if presupuesto.sync_status == SYNC_OK and not force:
                stats["omitidos"] += 1
                print(f"[OMITIDO] {etiqueta}: ya sincronizado.")
                continue

            try:
                status_code, response = _post_json(endpoint, payload, api_key, timeout)
                uuid_railway = _extraer_uuid(response)
                if not uuid_railway:
                    raise SyncError(
                        f"Respuesta HTTP {status_code} sin uuid/id: {response!r}"
                    )
                presupuesto.uuid_railway = uuid_railway
                presupuesto.sync_status = SYNC_OK
                presupuesto.synced_at = datetime.now(timezone.utc)
                presupuesto.sync_error = None
                presupuesto.railway_response = (
                    response if isinstance(response, dict) else {"raw": response}
                )
                session.commit()
                stats["enviados"] += 1
                print(f"[OK] {etiqueta}: HTTP {status_code} uuid={uuid_railway}")
            except SyncError as exc:
                stats["errores"] += 1
                presupuesto.sync_status = SYNC_ERROR
                presupuesto.sync_error = str(exc)
                session.commit()
                print(f"[ERROR] {etiqueta}: {exc}")

    return stats


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Sincroniza presupuestos APROBADO desde SQLite hacia Railway. "
            "Por defecto solo hace dry-run; usa --send para POST real."
        )
    )
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH, help="Ruta SQLite.")
    parser.add_argument(
        "--endpoint",
        default=os.getenv("DEPAFIX_RAILWAY_URL", DEFAULT_ENDPOINT),
        help="URL destino del POST.",
    )
    parser.add_argument(
        "--api-key",
        default=os.getenv("DEPAFIX_API_KEY"),
        help="API Key; por defecto DEPAFIX_API_KEY.",
    )
    parser.add_argument(
        "--id",
        action="append",
        dest="ids",
        help="propiedad_id a procesar; repetible. Permite revisar simulaciones en dry-run.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Permite estados no APROBADO o reenvío de ya sincronizados (solo pruebas).",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--send",
        action="store_true",
        help="Ejecuta POST real. Sin este flag el modo es dry-run.",
    )
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Fuerza dry-run (comportamiento por defecto).",
    )
    parser.add_argument("--timeout", type=int, default=30, help="Timeout HTTP en segundos.")
    parser.add_argument("--verbose", action="store_true", help="Log detallado.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )
    if args.send and not args.api_key:
        logging.warning(
            "DEPAFIX_API_KEY no configurada; se enviará sin X-API-Key. "
            "En producción configura la clave."
        )
    try:
        stats = sincronizar(
            db_path=args.db,
            endpoint=args.endpoint,
            api_key=args.api_key,
            ids=args.ids,
            force=args.force,
            send=args.send,
            timeout=args.timeout,
        )
    except Exception as exc:
        logging.error("Sincronización falló: %s", exc)
        if args.verbose:
            raise
        return 1
    print(
        "RESUMEN: "
        f"seleccionados={stats['seleccionados']} "
        f"enviados={stats['enviados']} "
        f"omitidos={stats['omitidos']} "
        f"errores={stats['errores']}"
    )
    return 1 if stats["errores"] else 0


if __name__ == "__main__":
    sys.exit(main())
