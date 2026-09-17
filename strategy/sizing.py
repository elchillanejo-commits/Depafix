"""Gestión dinámica de tamaño de posición basada en ATR y confianza."""
from config import RISK_PER_TRADE, ATR_SL_MULT


def calcular_tamano_posicion(
    capital_total: float,
    precio_actual: float,
    atr: float,
    confianza_score: float,
) -> float:
    """
    Tamaño de posición inverso a la volatilidad (ATR).
    confianza_score: 0.0 a 1.0 (del multi-timeframe).
    Retorna cantidad de unidades del activo.
    """
    if atr is None or atr <= 0 or precio_actual <= 0:
        return 0.0

    risk_usd = capital_total * RISK_PER_TRADE
    risk_ajustado = risk_usd * max(0.0, min(1.0, confianza_score))

    distancia_sl = atr * ATR_SL_MULT
    cantidad = risk_ajustado / distancia_sl

    # Validar que no exceda el capital
    max_usd = capital_total * 0.95
    if cantidad * precio_actual > max_usd:
        cantidad = max_usd / precio_actual

    return cantidad
