"""
orquestador_cripto.py -- corre el pipeline de ingesta (data_pipeline.py) y
recién después evalúa TradingLogic para cada par sobre velas 1H.

NOTA (2026-07-16): TradingLogic (src/trading/crypto_trader_agent.py) fue
reescrita -- ya no tiene evaluar()/constructor con activo=, ni la
confluencia fractal multi-temporalidad (1H/4H/1D) ni el stop-loss
estructural que describía esta versión antes. La API actual es
TradingLogic().analizar(velas, activo) sobre una sola temporalidad (1H), devolviendo
{senal, motivo, score, fibonacci, precio_actual, timestamp} -- sin
precio_entrada/stop_loss/formula/componentes. Este archivo fue actualizado
para llamar a esa API real; la lógica de señal en sí vive en
crypto_trader_agent.py, no acá.

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

TRADE_ROOT = Path("/home/ibar/Proyectos/05_TRADE_CRIPTO")  # reorg 2026-07-19
if str(TRADE_ROOT) not in sys.path:
    sys.path.insert(0, str(TRADE_ROOT))

from data_pipeline import PipelineVelas, PARES_DEFAULT
from crypto_trader_agent import TradingLogic
from injector import registrar_analisis

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def ejecutar_ciclo(exchange_id="binance", pares=None, limite=500):
    pares = pares or PARES_DEFAULT

    try:
        pipeline = PipelineVelas(exchange_id=exchange_id, pares=pares, limite=limite)
        pipeline.ejecutar()
    except Exception:
        # PipelineVelas.ejecutar() ya captura por combinación par/temporalidad
        # y nunca debería propagar (ver data_pipeline.py), pero si algo
        # explota en la construcción misma (p.ej. import roto, credencial
        # malformada) no queremos perder el traceback ni abortar sin loguear:
        # seguimos igual a evaluar TradingLogic con las velas que ya existan.
        logger.error("Fallo no controlado en la etapa de ingesta (pipeline):\n%s", traceback.format_exc())

    resultados = []
    for activo in pares:
        try:
            velas = pipeline.obtener_velas_para_analisis(activo, "1H", limite)
            resultado = TradingLogic().analizar(velas, activo)
            resultado["activo"] = activo
            resultados.append(resultado)
            logger.info("%s -> %s (%s)", activo, resultado.get("senal"), resultado.get("motivo"))

            if resultado.get("senal") in ("COMPRA", "VENTA"):
                try:
                    registrar_analisis(
                        activo=activo,
                        temporalidad="1H",
                        tipo=resultado.get("senal"),
                        entrada=resultado.get("precio_actual"),
                        stop=None,  # TradingLogic.analizar() ya no calcula stop-loss estructural
                        tp=None,
                        confluencias=resultado.get("fibonacci"),
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

    try:
        resultados = ejecutar_ciclo(
            exchange_id=args.exchange,
            pares=[p.strip() for p in args.pares.split(",") if p.strip()],
            limite=args.limite,
        )
    except Exception:
        # Red de seguridad final: invocado por cron, así que un traceback sin
        # capturar solo significa "el mail de cron dice FAIL" sin contexto. Acá
        # queda en el log con traceback completo y salimos con código != 0
        # para que cron/monitoreo lo detecte.
        logger.critical("Ciclo abortado por una excepción no controlada:\n%s", traceback.format_exc())
        sys.exit(1)

    if not resultados:
        logger.warning("El ciclo terminó sin resultados (posible falla de ingesta o de exchange).")
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
