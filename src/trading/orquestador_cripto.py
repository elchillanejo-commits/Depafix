"""
orquestador_cripto.py -- corre el pipeline de ingesta (data_pipeline.py) y
recién después evalúa TradingLogic para cada par, tal como pide la regla de
fractalidad: sin velas frescas en 1H/4H/1D no tiene sentido evaluar nada.

Pensado para invocarse por cron, igual que el resto de los agentes del
proyecto (core/trade_agent.py, core/auditor_precios_ia.py) -- no hay un
"orquestador" central tipo main.py en este repo que encadene pasos; main.py
es una app FastAPI de endpoints HTTP, no un runner de pipelines. Ver
main.py::POST /trading/ejecutar-cripto para el disparador manual vía HTTP.

Uso:
    python3 src/trading/orquestador_cripto.py [--exchange binance] [--pares BTC/USDT,ETH/USDT]
"""
import argparse
import logging
import sys
import traceback
from pathlib import Path

CORE_PATH = Path("/home/ibar/Proyectos/DepaFix")
if str(CORE_PATH) not in sys.path:
    sys.path.insert(0, str(CORE_PATH))

from src.trading.data_pipeline import PipelineVelas, PARES_DEFAULT
from src.trading.crypto_trader_agent import TradingLogic
from src.trading.injector import registrar_analisis

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def ejecutar_ciclo(exchange_id="binance", pares=None, limite=500):
    pares = pares or PARES_DEFAULT

    pipeline = PipelineVelas(exchange_id=exchange_id, pares=pares, limite=limite)
    pipeline.ejecutar()

    resultados = []
    for activo in pares:
        try:
            logic = TradingLogic(activo=activo)
            resultado = logic.evaluar()
            resultado["activo"] = activo
            resultados.append(resultado)
            logger.info("%s -> %s", activo, resultado.get("estado"))

            if resultado.get("estado") == "SEÑAL":
                try:
                    registrar_analisis(
                        activo=activo,
                        temporalidad="1H",
                        tipo=resultado.get("formula"),
                        entrada=resultado.get("precio_entrada"),
                        stop=resultado.get("stop_loss"),
                        tp=None,  # el manual no define take-profit fijo por fórmula; queda a criterio manual
                        confluencias=resultado.get("componentes"),
                    )
                except Exception:
                    logger.error("No se pudo registrar la señal de %s:\n%s", activo, traceback.format_exc())
        except Exception:
            logger.error("Excepción no controlada evaluando %s:\n%s", activo, traceback.format_exc())
            continue

    return resultados


def main():
    parser = argparse.ArgumentParser(description="Ingesta + evaluación TradingLogic por ciclo")
    parser.add_argument("--exchange", default="binance")
    parser.add_argument("--pares", default=",".join(PARES_DEFAULT))
    parser.add_argument("--limite", type=int, default=500)
    args = parser.parse_args()

    ejecutar_ciclo(
        exchange_id=args.exchange,
        pares=[p.strip() for p in args.pares.split(",") if p.strip()],
        limite=args.limite,
    )


if __name__ == "__main__":
    main()
