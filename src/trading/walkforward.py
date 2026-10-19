"""Validación walk-forward para estrategias de trading."""
from __future__ import annotations

from typing import Callable

import numpy as np
import pandas as pd

EstrategiaFn = Callable[[pd.DataFrame], pd.Series]
UMBRAL_ROBUSTEZ_PCT: float = 30.0


def sharpe_ratio(retornos: pd.Series, periodos_anuales: int = 365) -> float:
    if retornos is None or len(retornos) < 2:
        return 0.0
    std = float(retornos.std())
    if not np.isfinite(std) or abs(std) < 1e-12:
        return 0.0
    media = float(retornos.mean())
    return float((media / std) * np.sqrt(periodos_anuales))


def dividir_ventanas(
    df: pd.DataFrame,
    n_ventanas: int = 3,
    pct_entrenamiento: float = 0.7,
) -> list[tuple[pd.DataFrame, pd.DataFrame]]:
    if n_ventanas < 1:
        return []
    if not (0.0 < pct_entrenamiento < 1.0):
        return []
    n = len(df)
    if n < n_ventanas * 2:
        return []
    tam = n // n_ventanas
    if tam < 2:
        return []
    ventanas: list[tuple[pd.DataFrame, pd.DataFrame]] = []
    for i in range(n_ventanas):
        ini = i * tam
        fin = ini + tam if i < n_ventanas - 1 else n
        bloque = df.iloc[ini:fin]
        corte = int(len(bloque) * pct_entrenamiento)
        if corte < 1 or (len(bloque) - corte) < 1:
            return []
        ventanas.append((bloque.iloc[:corte], bloque.iloc[corte:]))
    return ventanas


def evaluar_estrategia(df: pd.DataFrame, funcion_estrategia: EstrategiaFn) -> dict:
    retornos = funcion_estrategia(df)
    if not isinstance(retornos, pd.Series):
        retornos = pd.Series(retornos, index=df.index)
    retornos = retornos.dropna()
    if len(retornos) == 0:
        return {"sharpe": 0.0, "n_trades": 0, "retorno_total": 0.0}
    return {
        "sharpe": sharpe_ratio(retornos),
        "n_trades": int((retornos != 0).sum()),
        "retorno_total": float((1.0 + retornos).prod() - 1.0),
    }


def walkforward(
    df: pd.DataFrame,
    funcion_estrategia: EstrategiaFn,
    n_ventanas: int = 3,
) -> dict:
    ventanas = dividir_ventanas(df, n_ventanas=n_ventanas)
    resultados: list[dict] = []
    for i, (train, test) in enumerate(ventanas):
        r_train = evaluar_estrategia(train, funcion_estrategia)
        r_test = evaluar_estrategia(test, funcion_estrategia)
        st = r_train["sharpe"]
        ss = r_test["sharpe"]
        deg = 0.0 if abs(st) < 1e-12 else ((st - ss) / abs(st)) * 100.0
        resultados.append({
            "i": i, "sharpe_train": st, "sharpe_test": ss, "degradacion_pct": deg,
        })
    if not resultados:
        return {
            "ventanas": [], "sharpe_promedio_train": 0.0,
            "sharpe_promedio_test": 0.0, "degradacion_promedio_pct": 0.0,
            "es_robusta": False,
        }
    return {
        "ventanas": resultados,
        "sharpe_promedio_train": float(np.mean([v["sharpe_train"] for v in resultados])),
        "sharpe_promedio_test": float(np.mean([v["sharpe_test"] for v in resultados])),
        "degradacion_promedio_pct": float(np.mean([v["degradacion_pct"] for v in resultados])),
        "es_robusta": float(np.mean([v["degradacion_pct"] for v in resultados])) < UMBRAL_ROBUSTEZ_PCT,
    }
