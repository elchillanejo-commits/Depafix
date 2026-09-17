#!/usr/bin/env python3
import sys, time, signal, logging, traceback
from datetime import datetime

sys.path.insert(0, "05_TRADE_CRIPTO")

# Logging PRIMERO, antes de cualquier import
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)-12s | %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("bot.log", encoding="utf-8", mode="a")
    ]
)
logger = logging.getLogger("Main")

# Ahora importamos
try:
    import config
    from bot_core import BotCore
    from bot_brain import Brain
    logger.info("✅ Modulos importados correctamente")
except Exception as e:
    logger.critical(f"❌ Error importando modulos: {e}")
    traceback.print_exc()
    sys.exit(1)

shutdown = False
def handler(s, f):
    global shutdown
    shutdown = True
    logger.info("🛑 Apagando bot graceful...")

signal.signal(signal.SIGINT, handler)
signal.signal(signal.SIGTERM, handler)

def main():
    logger.info("=" * 70)
    logger.info("🚀 DEPAFIX BOT INICIANDO")
    logger.info(f"Modo: {'PAPER' if getattr(config, 'PAPER_TRADING', True) else 'REAL'}")
    logger.info("=" * 70)

    try:
        config.validate_config()
        logger.info("✅ Config validada")
    except Exception as e:
        logger.error(f"❌ Config invalida: {e}")
        sys.exit(1)

    try:
        core = BotCore()
        brain = Brain(core)
        logger.info("✅ Bot inicializado")
    except Exception as e:
        logger.error(f"❌ Error inicializando bot: {e}")
        traceback.print_exc()
        sys.exit(1)

    # Backfill inicial (no bloqueante)
    logger.info("📊 Backfill inicial...")
    try:
        core.run_pipeline(config.PARES_TIMEFRAMES, backfill_days=1)
        logger.info("✅ Backfill completado")
    except Exception as e:
        logger.error(f"⚠️ Backfill fallo (continuando): {e}")
        traceback.print_exc()

    # Loop principal
    cycle = 0
    logger.info("🔁 Loop iniciado. Ctrl+C para detener.")
    while not shutdown:
        cycle += 1
        start = time.time()
        try:
            logger.info(f"{'─' * 50}")
            logger.info(f"🔄 CICLO #{cycle} | {datetime.now().strftime('%H:%M:%S')}")
            brain.run_cycle(config.PARES_TIMEFRAMES)
            elapsed = time.time() - start
            logger.info(f"⏱️ Ciclo #{cycle} en {elapsed:.1f}s")
        except Exception as e:
            logger.error(f"❌ Error ciclo #{cycle}: {e}")
            traceback.print_exc()

        if not shutdown:
            sleep_time = max(5, config.EXECUTION.get("loop_interval", 60) - (time.time() - start))
            logger.info(f"😴 Durmiendo {sleep_time:.0f}s...")
            time.sleep(sleep_time)

    logger.info("👋 Bot detenido")

if __name__ == "__main__":
    main()
