"""Stop Loss y Take Profit adaptativos basados en ATR."""
from config import ATR_SL_MULT, ATR_TP1_MULT, ATR_TP2_MULT, ATR_TP3_MULT


def calcular_niveles_salida(precio_entrada: float, atr: float, direccion: str = "LONG") -> dict:
    """Retorna SL, TP1, TP2, TP3."""
    if atr is None or atr <= 0:
        return {"sl": None, "tp1": None, "tp2": None, "tp3": None}

    if direccion == "LONG":
        return {
            "sl": precio_entrada - (ATR_SL_MULT * atr),
            "tp1": precio_entrada + (ATR_TP1_MULT * atr),
            "tp2": precio_entrada + (ATR_TP2_MULT * atr),
            "tp3": precio_entrada + (ATR_TP3_MULT * atr),
        }
    else:  # SHORT
        return {
            "sl": precio_entrada + (ATR_SL_MULT * atr),
            "tp1": precio_entrada - (ATR_TP1_MULT * atr),
            "tp2": precio_entrada - (ATR_TP2_MULT * atr),
            "tp3": precio_entrada - (ATR_TP3_MULT * atr),
        }


def evaluar_salidas(posicion: dict, precio_actual: float) -> str:
    """
    Evalúa si se debe cerrar parcial o totalmente.
    posicion: dict con entry_price, side, sl, tp1, tp2, tp3, tp1_hit, tp2_hit, tp3_hit
    Retorna: "HOLD", "CLOSE_SL", "TP1", "TP2", "TP3", "TRAIL"
    """
    side = posicion.get("side")
    sl = posicion.get("stop_loss")
    tp1 = posicion.get("take_profit_1")
    tp2 = posicion.get("take_profit_2")
    tp3 = posicion.get("take_profit_3")

    if side == "LONG":
        if sl is not None and precio_actual <= sl:
            return "CLOSE_SL"
        if tp1 is not None and precio_actual >= tp1 and not posicion.get("tp1_hit"):
            return "TP1"
        if tp2 is not None and precio_actual >= tp2 and not posicion.get("tp2_hit"):
            return "TP2"
        if tp3 is not None and precio_actual >= tp3 and not posicion.get("tp3_hit"):
            return "TP3"
    elif side == "SHORT":
        if sl is not None and precio_actual >= sl:
            return "CLOSE_SL"
        if tp1 is not None and precio_actual <= tp1 and not posicion.get("tp1_hit"):
            return "TP1"
        if tp2 is not None and precio_actual <= tp2 and not posicion.get("tp2_hit"):
            return "TP2"
        if tp3 is not None and precio_actual <= tp3 and not posicion.get("tp3_hit"):
            return "TP3"

    return "HOLD"
