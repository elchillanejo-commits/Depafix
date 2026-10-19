"""position_manager.py — Gestiona posiciones abiertas con trailing stops.

Fuente de verdad: tabla active_positions (no re-parsea historial).
Transacciones en operaciones_ejecutadas son INMUTABLES.

Fail-open: ante duda, no cierra.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal

import pandas as pd

from src.trading.trailing_stops import (
    atr_trail,
    bar_trail,
    debe_salir,
    ema_trail,
)

log = logging.getLogger(__name__)

TipoStop = Literal["bar", "atr", "ema"]
TIPO_STOP_DEFAULT: TipoStop = "atr"
HARD_STOP_PCT = 0.05  # 5% debajo de entry price (fail-safe duro)


@dataclass
class Posicion:
    id: str
    activo: str
    entry_price: float
    cantidad: float
    posicion_usd: float
    current_stop_loss: float
    hard_stop_loss: float
    buy_order_id: str | None


def get_posicion_abierta(client: Any, activo: str) -> Posicion | None:
    """Lee active_positions. None si no hay posición abierta."""
    try:
        resp = (
            client.table("active_positions")
            .select("id,activo,entry_price,cantidad,posicion_usd,"
                    "current_stop_loss,hard_stop_loss,buy_order_id")
            .eq("activo", activo)
            .order("opened_at", desc=True)
            .limit(1)
            .execute()
        )
    except Exception as e:
        log.warning("get_posicion_abierta %s falló: %s", activo, e)
        return None

    rows = resp.data or []
    if not rows:
        return None

    r = rows[0]
    return Posicion(
        id=str(r["id"]),
        activo=str(r["activo"]),
        entry_price=float(r["entry_price"]),
        cantidad=float(r.get("cantidad") or 0.0),
        posicion_usd=float(r.get("posicion_usd") or 0.0),
        current_stop_loss=float(r["current_stop_loss"]),
        hard_stop_loss=float(r["hard_stop_loss"]),
        buy_order_id=r.get("buy_order_id"),
    )


def registrar_posicion(
    client: Any,
    activo: str,
    entry_price: float,
    cantidad: float,
    posicion_usd: float,
    buy_order_id: str | None = None,
    stop_inicial: float | None = None,
) -> str | None:
    """Crea fila en active_positions al abrir COMPRA.

    Retorna el id de la fila creada, o None si falla.
    """
    hard_stop = stop_inicial if stop_inicial else entry_price * (1.0 - HARD_STOP_PCT)
    fila = {
        "activo": activo,
        "entry_price": entry_price,
        "cantidad": cantidad,
        "posicion_usd": posicion_usd,
        "buy_order_id": buy_order_id,
        "current_stop_loss": hard_stop,
        "hard_stop_loss": hard_stop,
    }
    try:
        resp = client.table("active_positions").insert(fila).execute()
        rows = resp.data or []
        return str(rows[0]["id"]) if rows else None
    except Exception as e:
        log.warning("registrar_posicion %s falló: %s", activo, e)
        return None


def cerrar_posicion(client: Any, posicion_id: str) -> bool:
    """Elimina la fila al cerrar VENTA."""
    try:
        client.table("active_positions").delete().eq("id", posicion_id).execute()
        return True
    except Exception as e:
        log.warning("cerrar_posicion %s falló: %s", posicion_id, e)
        return False


def _calcular_stop(df: pd.DataFrame, tipo: TipoStop) -> float:
    if tipo == "bar":
        return bar_trail(df, "LONG", bars_back=2)
    if tipo == "ema":
        return ema_trail(df, "LONG", ema_period=9)
    return atr_trail(df, "LONG", atr_period=3, atr_factor=3.0)


def debe_cerrar(
    df: pd.DataFrame,
    posicion: Posicion,
    tipo: TipoStop = TIPO_STOP_DEFAULT,
) -> tuple[bool, float, str]:
    """Decide cierre por trailing stop. Trailing LONG solo sube."""
    try:
        stop_calculado = _calcular_stop(df, tipo)
    except Exception as e:
        log.warning("_calcular_stop %s falló: %s", tipo, e)
        return (False, posicion.current_stop_loss, f"error_stop_{tipo}")

    nuevo_stop = max(posicion.current_stop_loss, stop_calculado)
    if nuevo_stop > posicion.hard_stop_loss + 1e-9:
        nuevo_stop = max(nuevo_stop, posicion.hard_stop_loss)

    try:
        cerrar = debe_salir(df, "LONG", nuevo_stop)
    except Exception as e:
        log.warning("debe_salir falló: %s", e)
        return (False, nuevo_stop, "error_debe_salir")

    if cerrar:
        return (True, nuevo_stop, f"trailing_stop_{tipo}")
    return (False, nuevo_stop, f"mantener_{tipo}")


def actualizar_stop(client: Any, posicion_id: str, nuevo_stop: float) -> bool:
    """UPDATE del current_stop_loss en active_positions (no toca operaciones)."""
    try:
        client.table("active_positions").update({
            "current_stop_loss": nuevo_stop,
            "last_updated_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", posicion_id).execute()
        return True
    except Exception as e:
        log.warning("actualizar_stop %s falló: %s", posicion_id, e)
        return False


def df_desde_velas(velas: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(velas)
    df = df.rename(columns={
        "cierre": "close", "apertura": "open",
        "maximo": "high", "minimo": "low",
        "volumen": "volume",
    })
    if "tiempo" in df.columns:
        df = df.sort_values("tiempo").reset_index(drop=True)
    return df
