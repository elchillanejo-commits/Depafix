"""Position sizing por régimen con Kelly fraccional 1/10.

Reglas:
    TREND_UP/TREND_DOWN -> capital * 0.01 * kelly_frac * 10
    RANGE               -> 0.0 (no operar)
    VOLATILE            -> capital * 0.005 * kelly_frac * 10
    desconocido         -> 0.0

Hard cap: 5% del capital por trade. Nunca más.
"""
from __future__ import annotations

KELLY_FRACCION_DEFAULT = 0.1
HARD_CAP_PCT = 0.05

_MULT_POR_REGIMEN: dict[str, float] = {
    "TREND_UP":   0.01,
    "TREND_DOWN": 0.01,
    "VOLATILE":   0.005,
    "RANGE":      0.0,
}


def kelly_optimo(win_rate: float, ratio_ganancia: float) -> float:
    """Kelly completo. Retorna fracción óptima del capital.

    Args:
        win_rate: probabilidad de ganar [0,1].
        ratio_ganancia: ganancia_media / perdida_media (>0).

    Returns:
        Fracción óptima clampada a [0.0, 0.25].

    Raises:
        ValueError: si win_rate fuera de [0,1] o ratio_ganancia <= 0.
    """
    if not (0.0 <= win_rate <= 1.0):
        raise ValueError(f"win_rate debe estar en [0,1], recibido {win_rate}")
    if ratio_ganancia <= 0:
        raise ValueError(f"ratio_ganancia debe ser >0, recibido {ratio_ganancia}")

    kelly = (win_rate - (1.0 - win_rate)) / ratio_ganancia
    if kelly <= 0.0:
        return 0.0
    return min(kelly, 0.25)


def get_position_size(
    capital: float,
    regimen: str,
    win_rate: float = 0.5,
    ratio_ganancia: float = 1.5,
    kelly_fraccion: float = KELLY_FRACCION_DEFAULT,
) -> float:
    """Tamaño de posición en USD para un trade según régimen y Kelly 1/10.

    Returns:
        USD a arriesgar. 0.0 si no debe operar.
    """
    if capital <= 0:
        return 0.0

    mult = _MULT_POR_REGIMEN.get(regimen.upper())
    if mult is None or mult == 0.0:
        return 0.0

    kelly = kelly_optimo(win_rate, ratio_ganancia)
    if kelly == 0.0:
        return 0.0

    pos_base = capital * mult * kelly_fraccion * 10
    return min(pos_base, capital * HARD_CAP_PCT)
