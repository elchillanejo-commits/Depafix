"""
crypto_trader_agent.py — Compat layer para v2 (2026-09-18)

Mantiene la interface `TradingLogic().analizar(velas)` que espera el
orquestador, pero internamente usa crypto_trader_agent_v2.analizar().

Devuelve dict compatible con el código existente del orquestador:
  - senal: COMPRA / VENTA / ESPERA
  - motivo: str con confluencias
  - score: max(score_alcista, score_bajista)
  - precio_actual
  - stop_loss, take_profit_1 (nuevos campos)
"""
from __future__ import annotations

import pandas as pd

from src.trading.crypto_trader_agent_v2 import analizar as analizar_v2


RENAME = {
    "apertura": "open", "maximo": "high", "minimo": "low",
    "cierre": "close", "volumen": "volume",
}


class TradingLogic:
    """Wrapper compatible con el orquestador existente."""

    def analizar(self, velas) -> dict:
        # Convertir lista → DataFrame
        if isinstance(velas, list):
            df = pd.DataFrame(velas)
        else:
            df = velas.copy()

        # Renombrar columnas de Supabase a estándar OHLCV
        df = df.rename(columns={k: v for k, v in RENAME.items() if k in df.columns})

        # Asegurar orden cronológico ascendente
        if "tiempo" in df.columns:
            df = df.sort_values("tiempo").reset_index(drop=True)

        # Llamar al motor v2
        r = analizar_v2(df)

        return {
            "senal": r.senal,
            "motivo": "; ".join(r.confluencia_detalle) or "Sin confluencias",
            "score": max(r.score_alcista, r.score_bajista),
            "precio_actual": r.precio_entrada,
            "stop_loss": r.stop_loss,
            "take_profit_1": r.take_profit_1,
            "score_alcista": r.score_alcista,
            "score_bajista": r.score_bajista,
            "confluencia_detalle": r.confluencia_detalle,
        }
