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
from datetime import datetime, timezone
from pathlib import Path
from decimal import Decimal
import traceback

BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

from core.db_manager import DatabaseManager
from src.trading.crypto_trader_agent_v2 import analizar
from src.trading.data_pipeline import PipelineVelas
from src.trading.position_sizer import get_position_size
from src.trading.position_manager import (
    get_posicion_abierta, registrar_posicion, cerrar_posicion,
    debe_cerrar, actualizar_stop, df_desde_velas,
)
import ccxt

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# ========== CONFIGURACIÓN ==========
MAX_POSICION_PCT_CAPITAL = 0.10
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

def registrar_senal(activo, senal, precio, motivo, puntuacion, modo, cantidad=None, ejecutada=False, orden_id=None, stop_loss=None, take_profit_1=None, confluencia_detalle=None, posicion_usd=None, regimen=None):
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
            'stop_loss': float(stop_loss) if stop_loss else None,
            'take_profit_1': float(take_profit_1) if take_profit_1 else None,
            'confluencia_detalle': confluencia_detalle,
            'posicion_usd': float(posicion_usd) if posicion_usd is not None else None,
            'regimen': regimen,
            'timestamp': datetime.now(timezone.utc).isoformat()
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

            # Position manager: build df + fetch posición abierta
            df_pm = df_desde_velas(velas) if len(velas) >= 10 else None
            db_pm = DatabaseManager.get_service_client()
            posicion = get_posicion_abierta(db_pm, activo)

            trading_logic = TradingLogic()
            resultado = trading_logic.analizar(velas)

            senal = resultado['senal']
            motivo = resultado.get('motivo', '')
            puntuacion = resultado.get('score', 0)
            precio_actual = resultado.get('precio_actual', velas[-1]['close'])

            # --- Filtro: TP mínimo para cubrir comisiones ---
            tp_tasa = 0.0
            if take_profit is not None and precio_actual > 0:
                tp_tasa = (float(take_profit) - precio_actual) / precio_actual
            
            # Kraken cobra ~0.26% + spread. Exigimos 1.72% mínimo.
            TP_MINIMO_TASA = 0.0172
            
            if tp_tasa < TP_MINIMO_TASA:
                motivo = f"{motivo}; COMPRA descartada: TP proyectado {tp_tasa:.2%} < mínimo {TP_MINIMO_TASA:.2%}"
                senal = "ESPERA"

            # Trailing stop: fuerza VENTA si rompe, actualiza stop si no
            if posicion and df_pm is not None:
                try:
                    cerrar, nuevo_stop, motivo_stop = debe_cerrar(df_pm, posicion, tipo="atr")
                    if cerrar:
                        senal = "VENTA"
                        motivo = f"Trailing stop: {motivo_stop}"
                        logger.info(f"🎯 {activo} trailing stop → VENTA")
                    else:
                        actualizar_stop(db_pm, posicion.id, nuevo_stop)
                except Exception as e:
                    logger.warning(f"position_manager override falló: {e}")

            logger.info(f"📊 {activo} -> {senal} | {motivo} | ${precio_actual:.2f}")

            # El sizer fija el riesgo en USD; el notional depende del stop y tiene un tope del 10%.
            regimen_temp = {"COMPRA": "TREND_UP", "VENTA": "TREND_DOWN", "ESPERA": "RANGE"}.get(senal, "RANGE")
            try:
                capital = float(os.getenv("CAPITAL_USD", "89"))
                riesgo_usd = get_position_size(capital, regimen_temp, win_rate=0.55, ratio_ganancia=1.5)
                posicion_usd = riesgo_usd

                if senal == "COMPRA" and riesgo_usd > 0:
                    posicion_usd = 0.0
                    stop_loss = resultado.get("stop_loss")
                    if stop_loss is None or precio_actual <= 0:
                        logger.warning(f"{activo}: precio o stop inválido para calcular la posición")
                    else:
                        distancia_stop = (precio_actual - float(stop_loss)) / precio_actual
                        if distancia_stop <= 0:
                            logger.warning(f"{activo}: stop de compra debe estar por debajo de la entrada")
                        else:
                            limite_notional = capital * MAX_POSICION_PCT_CAPITAL
                            posicion_usd = min(riesgo_usd / distancia_stop, limite_notional)

                texto_rag = " ".join(
                    str(item)
                    for item in (resultado.get("confluencia_detalle") or [])
                    if str(item).startswith("RAG:")
                ).casefold()
                palabras_riesgo = (
                    "cuidado", "trampa", "falso", "evitar", "peligro",
                )
                if posicion_usd > 0 and any(
                    palabra in texto_rag for palabra in palabras_riesgo
                ):
                    posicion_usd *= 0.5
                    logger.warning(
                        f"RAG advierte riesgo en {activo}; "
                        f"posicion_usd reducido a ${posicion_usd:.2f}"
                    )
            except Exception as e:
                logger.warning(f"⚠️ Sizer falló, degradando a 0.0: {e}")
                posicion_usd = 0.0
            logger.info(f"💰 {activo} | regimen={regimen_temp} | posicion_usd=${posicion_usd:.2f}")

            cantidad = None
            ejecutada = False
            orden_id = None

            if modo == 'real' and senal in ('COMPRA', 'VENTA'):
                balance = exchange.fetch_balance()

                if senal == 'COMPRA':
                    base = activo.split('/')[0]
                    base_free = balance.get(base, {}).get('free', 0) or 0
                    if base_free > 0:
                        logger.warning(f"⛔ Ya hay {base_free} {base} en cartera. No se comprará de nuevo.")
                        continue

                    usdt_free = balance.get('USDT', {}).get('free', 0) or 0
                    # Validamos contra el posicion_usd ya reducido por el RAG
                    if posicion_usd <= 0:
                        logger.warning(f"{activo}: compra omitida porque el sizing es 0.0 USD")
                    elif posicion_usd < float(MIN_ORDER_USDT):
                        logger.warning(
                            f"{activo}: compra omitida; ${posicion_usd:.2f} es menor "
                            f"que el mínimo de Kraken (${MIN_ORDER_USDT}).")
                    elif usdt_free < posicion_usd:
                        logger.warning(
                            f"Saldo insuficiente: {usdt_free:.2f} USDT < {posicion_usd:.2f} USDT"
                        )
                    else:
                        quantity = posicion_usd / precio_actual
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
                orden_id=orden_id,
                stop_loss=resultado.get('stop_loss'),
                take_profit_1=resultado.get('take_profit_1'),
                confluencia_detalle=resultado.get('confluencia_detalle'),
                posicion_usd=posicion_usd,
                regimen=regimen_temp)

            # Persistencia en active_positions
            try:
                if senal == "COMPRA" and posicion_usd and posicion_usd > 0 and not posicion:
                    registrar_posicion(db_pm, activo, precio_actual, cantidad or 0,
                                       posicion_usd, buy_order_id=orden_id)
                    logger.info(f"💼 Posición abierta: {activo}")
                elif senal == "VENTA" and posicion:
                    cerrar_posicion(db_pm, posicion.id)
                    logger.info(f"💼 Posición cerrada: {activo}")
            except Exception as e:
                logger.warning(f"error persistencia posición: {e}")

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
