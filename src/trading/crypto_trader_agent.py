"""
crypto_trader_agent.py -- TradingLogic implementa las fórmulas de confluencia
del "Manual Maestro: Trading Profesional" (~/docs/Comercio/Trade resumen.pdf).

Genera SEÑALES, no ejecuta órdenes -- igual que core/trade_agent.py, esto es
apoyo a la decisión, no un bot que opera solo.

Fórmulas implementadas (Módulo 4 del manual):
    Alcista Standard    = Soporte Estático + Fibo 0.618-0.786 + Testeo EMA50
                           + RSI en Sobreventa
    Institucional Avanzada = Order Block Válido + Mitigación de FVG
                              + Barrido de Liquidez Minorista

Reglas de oro aplicadas:
    1. Fractalidad: una entrada en 1H solo es válida si hay una zona de
       soporte en 4H o 1D en la misma región de precio. Si no hay
       confluencia, se devuelve ESTADO: ESPERA sin evaluar nada más.
    2. Protección: toda señal incluye un Stop Loss técnico basado en
       estructura (debajo de la zona de soporte / order block / mecha del
       barrido de liquidez que originó la entrada), nunca un valor arbitrario.

IMPORTANTE -- estado de los datos (2026-07-15): no existe todavía ninguna
ingesta real de velas cripto en este proyecto (se verificó explícitamente:
sin integración de exchange, sin tabla OHLC previa). Este archivo define el
esquema esperado (sql/create_velas_cripto.sql) y la lógica completa contra
él, pero mientras esa tabla esté vacía, evaluar() siempre devolverá
ESTADO: ESPERA por falta de datos -- eso es correcto, no un bug.
"""
import logging
import sys
import traceback
from pathlib import Path

CORE_PATH = Path("/home/ibar/Proyectos/DepaFix")
if str(CORE_PATH) not in sys.path:
    sys.path.insert(0, str(CORE_PATH))

from core.db_manager import DatabaseManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

TABLA_VELAS = "velas_cripto"
MIN_VELAS = 30  # mínimo para que EMA50/RSI/pivots tengan sentido (EMA50 real pide más; ver _ema)


# ---------------------------------------------------------------------------
# Indicadores puros: sin I/O, testeables con velas sintéticas.
# Una "vela" es un dict con claves: tiempo, open, high, low, close, volume.
# ---------------------------------------------------------------------------

def _ema(cierres, periodo):
    """EMA estándar. Si hay menos velas que 'periodo', usa el promedio simple
    disponible como semilla (mejor una EMA aproximada con pocos datos que
    ninguna)."""
    if not cierres:
        return None
    k = 2 / (periodo + 1)
    ema = sum(cierres[:min(periodo, len(cierres))]) / min(periodo, len(cierres))
    for precio in cierres[min(periodo, len(cierres)):]:
        ema = precio * k + ema * (1 - k)
    return ema


def _rsi(cierres, periodo=14):
    """RSI estándar (Wilder). Devuelve None si no hay suficientes velas."""
    if len(cierres) < periodo + 1:
        return None
    ganancias, perdidas = [], []
    for i in range(1, len(cierres)):
        delta = cierres[i] - cierres[i - 1]
        ganancias.append(max(delta, 0))
        perdidas.append(max(-delta, 0))
    avg_gain = sum(ganancias[:periodo]) / periodo
    avg_loss = sum(perdidas[:periodo]) / periodo
    for g, p in zip(ganancias[periodo:], perdidas[periodo:]):
        avg_gain = (avg_gain * (periodo - 1) + g) / periodo
        avg_loss = (avg_loss * (periodo - 1) + p) / periodo
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def _pivots(velas, izquierda=2, derecha=2, tipo="bajo"):
    """Fractales simples: una vela es pivot-bajo si su low es el mínimo entre
    'izquierda' velas antes y 'derecha' velas después (pivot-alto, análogo con
    high). Son las "vueltas del precio en forma de V" que el manual usa para
    trazar soportes/resistencias como zonas."""
    pivots = []
    campo = "low" if tipo == "bajo" else "high"
    cmp = min if tipo == "bajo" else max
    for i in range(izquierda, len(velas) - derecha):
        ventana = velas[i - izquierda:i + derecha + 1]
        valores = [v[campo] for v in ventana]
        if velas[i][campo] == cmp(valores):
            pivots.append(velas[i])
    return pivots


def _zonas_soporte(velas, tolerancia_pct=0.005):
    """Agrupa pivots-bajo cercanos entre sí (dentro de tolerancia_pct) en
    zonas [min,max], como pide el manual ("zonas, no líneas")."""
    pivots = sorted(_pivots(velas, tipo="bajo"), key=lambda v: v["low"])
    zonas = []
    for p in pivots:
        agregado = False
        for z in zonas:
            centro = (z["min"] + z["max"]) / 2
            if abs(p["low"] - centro) / centro <= tolerancia_pct:
                z["min"] = min(z["min"], p["low"])
                z["max"] = max(z["max"], p["low"])
                z["toques"] += 1
                agregado = True
                break
        if not agregado:
            zonas.append({"min": p["low"], "max": p["low"], "toques": 1})
    return zonas


def _fibonacci_niveles(alto, bajo):
    """Retroceso de Fibonacci optimizado (Módulo 3.2): 0, 0.5, Golden Pocket
    (0.618-0.786), 1.0, medidos desde 'bajo' (0.0, inicio del impulso desde
    abajo) hasta 'alto' (1.0)."""
    rango = alto - bajo
    return {
        "0.0": bajo,
        "0.5": bajo + rango * 0.5,
        "golden_pocket_inicio": bajo + rango * 0.618,
        "golden_pocket_fin": bajo + rango * 0.786,
        "1.0": alto,
    }


def _detectar_fvg(velas):
    """FVG alcista (Módulo 3.3): vela1.high < vela3.low, dejando el cuerpo de
    vela2 expuesto. La zona [vela1.high, vela3.low] queda "mitigada" si alguna
    vela posterior tradea de vuelta dentro de ella."""
    fvgs = []
    for i in range(2, len(velas)):
        v1, v3 = velas[i - 2], velas[i]
        if v1["high"] < v3["low"]:
            zona = {"tipo": "alcista", "min": v1["high"], "max": v3["low"], "idx": i, "mitigado": False}
            for v_post in velas[i + 1:]:
                if v_post["low"] <= zona["max"]:
                    zona["mitigado"] = True
                    break
            fvgs.append(zona)
    return fvgs


def _detectar_order_blocks(velas, fvgs):
    """Order block alcista (Módulo 3.4): última vela bajista antes de un
    impulso que rompe la estructura previa (máximo reciente) y deja al menos
    un FVG a su paso. Se invalida si una vela posterior cierra por debajo del
    mínimo del bloque (el cuerpo lo "atraviesa por completo")."""
    blocks = []
    for fvg in fvgs:
        if fvg["tipo"] != "alcista" or fvg["idx"] < 2:
            continue
        idx_impulso = fvg["idx"] - 1  # vela que generó el FVG junto a vela1/vela3
        # Buscar hacia atrás la última vela bajista antes del impulso: el order block.
        j = idx_impulso
        while j >= 0 and velas[j]["close"] >= velas[j]["open"]:
            j -= 1
        if j < 0:
            continue
        ob_vela = velas[j]
        maximo_previo = max((v["high"] for v in velas[max(0, j - 10):j]), default=None)
        if maximo_previo is None or velas[idx_impulso]["high"] <= maximo_previo:
            continue  # no rompió estructura previa: no califica como order block
        valido = not any(v["close"] < ob_vela["low"] for v in velas[j + 1:])
        blocks.append({
            "min": ob_vela["low"], "max": ob_vela["open"],
            "idx": j, "valido": valido,
        })
    return blocks


def _detectar_barrido_liquidez(velas, nivel, ventana=5):
    """Barrido de liquidez / fakeout (Módulo 2.3): una vela reciente mete
    mecha por debajo de 'nivel' pero cierra de vuelta por encima -> liquidez
    minorista barrida antes de un movimiento real."""
    for vela in velas[-ventana:]:
        if vela["low"] < nivel <= vela["close"]:
            return True
    return False


# ---------------------------------------------------------------------------
# TradingLogic: orquestación + acceso a datos.
# ---------------------------------------------------------------------------

class TradingLogic:
    def __init__(self, activo="BTC/USDT", rsi_periodo=14, rsi_sobreventa=30,
                 ema_periodo=50, tolerancia_zona_pct=0.005):
        self.activo = activo
        self.rsi_periodo = rsi_periodo
        # El manual pide "RSI en Sobreventa" sin dar el umbral numérico exacto;
        # 30 es el estándar de la industria (Wilder) y se deja configurable.
        self.rsi_sobreventa = rsi_sobreventa
        self.ema_periodo = ema_periodo
        self.tolerancia_zona_pct = tolerancia_zona_pct
        self.db = None
        try:
            self.db = DatabaseManager.get_client()
        except Exception as e:
            logger.error("No se pudo inicializar el cliente de Supabase: %s", e)

    # ---------- acceso a datos, robusto a fallas de red ----------

    def _obtener_velas(self, temporalidad, limite=200):
        if not self.db:
            return []
        try:
            resp = (
                self.db.table(TABLA_VELAS)
                .select("tiempo,open,high,low,close,volume")
                .eq("activo", self.activo)
                .eq("temporalidad", temporalidad)
                .order("tiempo", desc=True)
                .limit(limite)
                .execute()
            )
            return list(reversed(resp.data or []))  # orden ascendente para los indicadores
        except Exception as e:
            logger.error(
                "Fallo de red/consulta leyendo %s (%s, %s): %s",
                TABLA_VELAS, self.activo, temporalidad, e,
            )
            return []

    # ---------- regla de oro 1: fractalidad ----------

    def _confluencia_htf(self, precio_actual, velas_4h, velas_1d):
        """Devuelve la zona de soporte de temporalidad alta (4H o 1D, se
        prioriza 1D por mandar más) donde cae precio_actual, o None si no hay
        ninguna -- en cuyo caso el llamador debe devolver ESPERA sin seguir
        evaluando fórmulas."""
        for velas_htf in (velas_1d, velas_4h):
            if len(velas_htf) < MIN_VELAS:
                continue
            for zona in _zonas_soporte(velas_htf, self.tolerancia_zona_pct):
                if zona["min"] <= precio_actual <= zona["max"]:
                    return zona
        return None

    # ---------- fórmulas de entrada (Módulo 4) ----------

    def _formula_alcista_standard(self, velas_1h, zona_soporte_1h):
        cierres = [v["close"] for v in velas_1h]
        ema50 = _ema(cierres, self.ema_periodo)
        rsi = _rsi(cierres, self.rsi_periodo)
        if ema50 is None or rsi is None:
            return None

        precio_actual = cierres[-1]
        alto_reciente = max(v["high"] for v in velas_1h[-50:])
        fibo = _fibonacci_niveles(alto_reciente, zona_soporte_1h["min"])
        en_golden_pocket = fibo["golden_pocket_inicio"] <= precio_actual <= fibo["golden_pocket_fin"]
        testeo_ema50 = abs(precio_actual - ema50) / ema50 <= self.tolerancia_zona_pct
        en_sobreventa = rsi <= self.rsi_sobreventa

        if en_golden_pocket and testeo_ema50 and en_sobreventa:
            return {
                "formula": "Alcista Standard",
                "componentes": {
                    "soporte_estatico": zona_soporte_1h,
                    "fibo_golden_pocket": (fibo["golden_pocket_inicio"], fibo["golden_pocket_fin"]),
                    "ema50": round(ema50, 2),
                    "rsi": round(rsi, 2),
                },
                "precio_entrada": precio_actual,
                "sl_referencia": zona_soporte_1h["min"],
            }
        return None

    def _formula_institucional_avanzada(self, velas_1h, zona_soporte_1h):
        fvgs = _detectar_fvg(velas_1h)
        blocks = _detectar_order_blocks(velas_1h, fvgs)
        precio_actual = velas_1h[-1]["close"]

        for block in blocks:
            if not block["valido"]:
                continue
            fvg_asociado = next(
                (f for f in fvgs if f["idx"] > block["idx"] and f["mitigado"]), None
            )
            if not fvg_asociado:
                continue
            barrido = _detectar_barrido_liquidez(velas_1h, block["min"])
            en_zona_entrada = (
                block["min"] <= precio_actual <= block["max"]
                or fvg_asociado["min"] <= precio_actual <= fvg_asociado["max"]
            )
            if not en_zona_entrada or not barrido:
                continue
            return {
                "formula": "Institucional Avanzada",
                "componentes": {
                    "order_block": block,
                    "fvg_mitigado": fvg_asociado,
                    "barrido_liquidez": True,
                },
                "precio_entrada": precio_actual,
                "sl_referencia": block["min"],
            }
        return None

    # ---------- stop loss técnico (regla de oro 2: protección) ----------

    def _stop_loss_tecnico(self, velas_1h, sl_referencia, margen_pct=0.002):
        """SL debajo de la estructura que originó la entrada (soporte/order
        block), con un margen chico para no saltar por ruido de mecha. Nunca
        un valor arbitrario/porcentual sobre el precio de entrada."""
        return round(sl_referencia * (1 - margen_pct), 8)

    # ---------- orquestación ----------

    def evaluar(self):
        """Punto de entrada único. Nunca lanza excepción hacia afuera: ante
        cualquier fallo devuelve ESTADO: ESPERA con el motivo, siguiendo la
        regla de oro de protección (mejor no operar que operar a ciegas)."""
        try:
            velas_1h = self._obtener_velas("1H")
            velas_4h = self._obtener_velas("4H")
            velas_1d = self._obtener_velas("1D")

            if len(velas_1h) < MIN_VELAS:
                return {"estado": "ESPERA", "motivo": f"datos insuficientes en 1H ({len(velas_1h)}/{MIN_VELAS} velas)"}
            if not velas_4h and not velas_1d:
                return {"estado": "ESPERA", "motivo": "sin velas 4H ni 1D -- no se puede aplicar la regla de fractalidad"}

            precio_actual = velas_1h[-1]["close"]

            # Regla de oro 1: fractalidad -- manda antes que cualquier fórmula.
            zona_htf = self._confluencia_htf(precio_actual, velas_4h, velas_1d)
            if not zona_htf:
                return {
                    "estado": "ESPERA",
                    "motivo": "sin confluencia entre 1H y soporte de 4H/1D (regla de fractalidad)",
                    "precio_actual": precio_actual,
                }

            for evaluador in (self._formula_alcista_standard, self._formula_institucional_avanzada):
                try:
                    senal = evaluador(velas_1h, zona_htf)
                except Exception:
                    logger.error("Excepción evaluando %s:\n%s", evaluador.__name__, traceback.format_exc())
                    continue
                if senal:
                    senal["estado"] = "SEÑAL"
                    senal["activo"] = self.activo
                    senal["zona_confluencia_htf"] = zona_htf
                    senal["stop_loss"] = self._stop_loss_tecnico(velas_1h, senal["sl_referencia"])
                    return senal

            return {
                "estado": "ESPERA",
                "motivo": "confluencia 1H/4H-1D encontrada, pero ninguna fórmula de entrada se cumple todavía",
                "zona_confluencia_htf": zona_htf,
                "precio_actual": precio_actual,
            }
        except Exception:
            logger.error("Excepción no controlada en evaluar():\n%s", traceback.format_exc())
            return {"estado": "ESPERA", "motivo": "excepción no controlada, ver log"}


class CryptoTraderAgent:
    """Wrapper delegado a TradingLogic; se mantiene por compatibilidad con
    quien ya importe CryptoTraderAgent."""

    def __init__(self, balance=20000, activo="BTC/USDT"):
        self.balance = balance
        self.risk_per_trade = 0.01  # Conservador: 1% de riesgo
        self.logic = TradingLogic(activo=activo)

    def analizar_mercado(self):
        return self.logic.evaluar()

    def ejecutar_gestion_riesgo(self, senal):
        """Tamaño de posición para self.balance según 1% de riesgo, usando el
        SL técnico de la señal. Solo aplica si estado == 'SEÑAL'."""
        if senal.get("estado") != "SEÑAL":
            return None
        riesgo_por_unidad = abs(senal["precio_entrada"] - senal["stop_loss"])
        if riesgo_por_unidad <= 0:
            return None
        capital_en_riesgo = self.balance * self.risk_per_trade
        return {
            "tamano_posicion": round(capital_en_riesgo / riesgo_por_unidad, 8),
            "capital_en_riesgo": capital_en_riesgo,
        }


if __name__ == "__main__":
    agente = CryptoTraderAgent()
    resultado = agente.analizar_mercado()
    print(resultado)
