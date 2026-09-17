"""Detección de régimen de mercado: Tendencia vs Rango via ADX."""
from config import ADX_TREND_THRESHOLD, ADX_RANGE_THRESHOLD


def detectar_regimen(adx: float) -> str:
    """Retorna TENDENCIA, RANGO o TRANSICION."""
    if adx is None:
        return "UNKNOWN"
    if adx > ADX_TREND_THRESHOLD:
        return "TENDENCIA"
    if adx < ADX_RANGE_THRESHOLD:
        return "RANGO"
    return "TRANSICION"
