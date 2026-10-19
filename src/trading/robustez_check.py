"""robustez_check.py — Evaluación walk-forward para supervisor.

Se ejecuta 1/día para verificar que la estrategia sigue siendo robusta.
Fail-open: si no hay datos suficientes o falla, retorna robusta=None
(sin veredicto), NUNCA pausa el bot por sí mismo.

Regla: robusta=True solo si TODOS los pares evaluados son robustos.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import pandas as pd

from src.trading.crypto_trader_agent import TradingLogic
from src.trading.walkforward import walkforward

log = logging.getLogger(__name__)

MIN_VELAS = 400
N_VENTANAS = 2
LIMITE_FETCH = 500


def _calcular_senales(df: pd.DataFrame) -> pd.Series:
    """Precomputa señales bar a bar, sin lookahead."""
    tl = TradingLogic()
    senales: list[str] = []
    for i in range(len(df)):
        try:
            r = tl.analizar(df.iloc[: i + 1].to_dict("records"))
            senales.append(str(r.get("senal", "ESPERA")))
        except Exception:
            senales.append("ESPERA")
    return pd.Series(senales, index=df.index)


def _retornos_desde_senales(df: pd.DataFrame, senales: pd.Series) -> pd.Series:
    """Retorno del bar i = señal del bar i-1 × cambio % del bar i."""
    pct = df["close"].pct_change().fillna(0.0)
    signo = senales.shift(1).fillna("ESPERA").map(
        {"COMPRA": 1.0, "VENTA": -1.0, "ESPERA": 0.0}
    )
    return (signo * pct).astype(float)


def evaluar_par(df: pd.DataFrame, n_ventanas: int = N_VENTANAS) -> dict[str, Any]:
    """Walkforward sobre un df ya preparado. Fail-open."""
    if len(df) < MIN_VELAS:
        return {"estado": "pocos_datos", "velas": len(df), "min_requerido": MIN_VELAS}

    try:
        senales = _calcular_senales(df)
        retornos = _retornos_desde_senales(df, senales)

        def estrategia(d: pd.DataFrame) -> pd.Series:
            return retornos.loc[d.index]

        wf = walkforward(df, estrategia, n_ventanas=n_ventanas)
        return {
            "estado": "ok",
            "es_robusta": bool(wf["es_robusta"]),
            "degradacion_pct": float(wf["degradacion_promedio_pct"]),
            "sharpe_train": float(wf["sharpe_promedio_train"]),
            "sharpe_test": float(wf["sharpe_promedio_test"]),
        }
    except Exception as e:
        log.warning("evaluar_par falló: %s", e)
        return {"estado": "error", "detalle": str(e)[:200]}


async def validar_robustez(
    client: Any,
    activos: list[str],
    limite: int = LIMITE_FETCH,
) -> dict[str, Any]:
    """Evalúa robustez multi-activo. Fail-open.

    Retorna:
        {
          "robusta": True | False | None,
          "motivo": str,
          "por_activo": {par: {...}}
        }
    """
    por_activo: dict[str, dict] = {}

    for par in activos:
        try:
            resp = (
                client.table("velas_cripto")
                .select("*")
                .eq("par", par)
                .eq("temporalidad", "1H")
                .order("tiempo", desc=True)
                .limit(limite)
                .execute()
            )
            rows = resp.data or []
        except Exception as e:
            log.warning("fetch velas %s falló: %s", par, e)
            por_activo[par] = {"estado": "fetch_error", "detalle": str(e)[:100]}
            continue

        if len(rows) < MIN_VELAS:
            por_activo[par] = {
                "estado": "pocos_datos",
                "velas": len(rows),
                "min_requerido": MIN_VELAS,
            }
            continue

        df = pd.DataFrame(rows).rename(columns={"cierre": "close"})
        df = df.sort_values("tiempo").reset_index(drop=True)
        por_activo[par] = await asyncio.to_thread(evaluar_par, df, N_VENTANAS)

    pares_ok = [r for r in por_activo.values() if r.get("estado") == "ok"]
    if not pares_ok:
        return {
            "robusta": None,
            "motivo": "sin_datos_suficientes",
            "por_activo": por_activo,
        }

    robusta = all(r.get("es_robusta", False) for r in pares_ok)
    return {"robusta": robusta, "motivo": "ok", "por_activo": por_activo}
