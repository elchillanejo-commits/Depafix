#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
trading_orchestrator.py - Orquestador de trading 24/7 con órdenes reales
"""
import os
import sys
import time
import logging
import argparse
from datetime import datetime
from pathlib import Path
from decimal import Decimal
import traceback

BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

from core.db_manager import DatabaseManager
from src.trading.crypto_trader_agent import TradingLogic
from src.trading.data_pipeline import PipelineVelas
import ccxt

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# ========== CONFIGURACIÓN ==========
TRADE_AMOUNT_USDT = Decimal("6.50")
MIN_ORDER_USDT = Decimal("6.49")

def parse_args():
    parser = argparse.ArgumentParser(description='Trading Orchestrator')
    parser.add_argument('--exchange', default='binance', help='Exchange: binance, kraken')
    parser.add_argument('--activos', default='BTC/USDT,SOL/USDT', help='Pares separados por coma')
    parser.add_argument('--intervalo', type=int, default=300, help='Segundos entre ciclos')
    parser.add_argument('--modo', default='simulacion', choices=['simulacion', 'real'], help='Modo de operación')
    parser.add_argument('--una-vez', action='store_true', help='Ejecutar un solo ciclo y salir')
    parser.add_argument('--limite', type=int, default=100, help='Velas a descargar por ciclo')
    return parser.parse_args()

def get_exchange(exchange_id):
    """Cliente autenticado del exchange -- solo se llama en modo real."""
    if exchange_id == 'binance':
        exchange = ccxt.binance({
            'apiKey': os.getenv('BINANCE_API_KEY'),
            'secret': os.getenv('BINANCE_SECRET_KEY'),
            'enableRateLimit': True,
            'options': {'defaultType': 'spot'}
        })
    elif exchange_id == 'kraken':
        exchange = ccxt.kraken({
            'apiKey': os.getenv('KRAKEN_API_KEY'),
            'secret': os.getenv('KRAKEN_SECRET_KEY'),
            'enableRateLimit': True
        })
    else:
        raise ValueError(f"Exchange no soportado: {exchange_id}")
    return exchange

def execute_order(exchange, symbol, side, quantity, price):
    """Ejecuta una orden de mercado real. side: 'buy' o 'sell'."""
    try:
        quantity = float(exchange.amount_to_precision(symbol, quantity))
        notional = quantity * price

        if notional < float(MIN_ORDER_USDT) - 0.01:
            logger.warning(f"Monto muy pequeño: {quantity} {symbol} (${notional:.4f} < ${MIN_ORDER_USDT})")
            return None

        logger.info(f"💰 Ejecutando orden {side} {quantity} {symbol} a ${price:.2f}")
        order = exchange.create_market_order(symbol, side, quantity)
        logger.info(f"✅ Orden ejecutada: {order}")
        return order
    except ccxt.InsufficientFunds as e:
        logger.error(f"❌ Saldo insuficiente para {side} {symbol}: {e}")
        return None
    except Exception as e:
        logger.error(f"❌ Error ejecutando orden: {e}")
        return None

def registrar_senal(activo, senal, precio, motivo, puntuacion, modo, cantidad=None, ejecutada=False, orden_id=None):
    """Guarda la señal en operaciones_ejecutadas"""
    try:
        data = {
            'activo': activo,
            'temporalidad': '1H',
            'senal': senal,
            'precio_entrada': float(precio),
            'precio_salida': None,
            'cantidad': float(cantidad) if cantidad else None,
            'motivo': motivo,
            'puntuacion_confluencia': puntuacion,
            'ejecutada': ejecutada,
            'orden_id': orden_id,
            'timestamp': datetime.utcnow().isoformat()
        }
        db_client = DatabaseManager.get_service_client()
        result = db_client.table('operaciones_ejecutadas').insert(data).execute()
        logger.info(f"📝 Señal registrada: {activo} | {senal} | ${precio:.2f} | {motivo}")
        return result
    except Exception as e:
        logger.error(f"❌ Error registrando señal: {e}")
        return None

def ejecutar_ciclo(exchange, exchange_id, activos, limite, modo):
    """Ejecuta un ciclo de trading"""
    logger.info(f"🔄 Ciclo iniciado: {exchange_id} | {','.join(activos)}")

    pipeline = PipelineVelas(exchange_id)

    for activo in activos:
        try:
            velas = pipeline.obtener_velas(activo, '1H', limite)
            if not velas:
                logger.warning(f"No hay datos para {activo}")
                continue

            trading_logic = TradingLogic()
            resultado = trading_logic.analizar(velas)

            senal = resultado['senal']
            motivo = resultado.get('motivo', '')
            puntuacion = resultado.get('score', 0)
            precio_actual = resultado.get('precio_actual', velas[-1]['close'])

            logger.info(f"📊 {activo} -> {senal} | {motivo} | ${precio_actual:.2f}")

            cantidad = None
            ejecutada = False
            orden_id = None

            if modo == 'real' and senal in ('COMPRA', 'VENTA'):
                balance = exchange.fetch_balance()

                if senal == 'COMPRA':
                    db = DatabaseManager.get_service_client()
                    ultima = db.table('operaciones_ejecutadas').select('senal','ejecutada').eq('activo', activo).order('timestamp', desc=True).limit(1).execute()
                    if ultima.data and ultima.data[0]['senal'] == 'COMPRA' and ultima.data[0]['ejecutada'] == True:
                        logger.warning(f"⛔ Ya hay posición abierta en {activo}. No se comprará de nuevo.")
                        continue

                    usdt_free = balance.get('USDT', {}).get('free', 0) or 0
                    if usdt_free < float(TRADE_AMOUNT_USDT):
                        logger.warning(f"Saldo insuficiente: {usdt_free:.2f} USDT < {TRADE_AMOUNT_USDT}")
                    else:
                        quantity = float(TRADE_AMOUNT_USDT) / precio_actual
                        order = execute_order(exchange, activo, 'buy', quantity, precio_actual)
                        if order:
                            ejecutada = True
                            cantidad = order.get('filled') or quantity
                            orden_id = order.get('id')

                elif senal == 'VENTA':
                    base = activo.split('/')[0]
                    balance_free = balance.get(base, {}).get('free', 0) or 0
                    if balance_free <= 0:
                        logger.warning(f"No hay {base} para vender")
                    else:
                        order = execute_order(exchange, activo, 'sell', balance_free, precio_actual)
                        if order:
                            ejecutada = True
                            cantidad = order.get('filled') or balance_free
                            orden_id = order.get('id')

            registrar_senal(
                activo=activo,
                senal=senal,
                precio=precio_actual,
                motivo=motivo,
                puntuacion=puntuacion,
                modo=modo,
                cantidad=cantidad,
                ejecutada=ejecutada,
                orden_id=orden_id
            )

        except Exception as e:
            logger.error(f"❌ Error procesando {activo}: {e}")
            traceback.print_exc()

    logger.info("✅ Ciclo completado")

def main():
    args = parse_args()
    
    logger.info(f"🧠 Siegfried Trading Agent iniciado")
    logger.info(f"   Exchange: {args.exchange}")
    logger.info(f"   Activos: {args.activos}")
    logger.info(f"   Modo: {args.modo}")
    logger.info(f"   Intervalo: {args.intervalo}s")
    
    activos = [a.strip() for a in args.activos.split(',')]

    exchange = get_exchange(args.exchange) if args.modo == 'real' else None

    while True:
        try:
            ejecutar_ciclo(exchange, args.exchange, activos, args.limite, args.modo)
            if args.una_vez:
                break
            time.sleep(args.intervalo)
        except KeyboardInterrupt:
            logger.info("👋 Interrupción recibida. Saliendo...")
            break
        except Exception as e:
            logger.error(f"❌ Error en ciclo principal: {e}")
            traceback.print_exc()
            time.sleep(args.intervalo)

if __name__ == '__main__':
    main()
