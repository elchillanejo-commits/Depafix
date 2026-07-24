#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
trading_orchestrator.py - Orquestador de trading 24/7 para Binance/Kraken
Siegfried Trading Agent
"""

import os
import sys
import time
import logging
import argparse
from datetime import datetime
from pathlib import Path
import traceback

# Agregar raíz del proyecto al path
BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

from core.db_manager import db
from src.trading.crypto_trader_agent import TradingLogic
from src.trading.data_pipeline import PipelineVelas

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

def parse_args():
    parser = argparse.ArgumentParser(description='Trading Orchestrator')
    parser.add_argument('--exchange', default='binance', help='Exchange: binance, kraken')
    parser.add_argument('--activos', default='BTC/USDT,SOL/USDT', help='Pares separados por coma')
    parser.add_argument('--intervalo', type=int, default=300, help='Segundos entre ciclos')
    parser.add_argument('--modo', default='simulacion', choices=['simulacion', 'real'], help='Modo de operación')
    parser.add_argument('--una-vez', action='store_true', help='Ejecutar un solo ciclo y salir')
    parser.add_argument('--limite', type=int, default=100, help='Velas a descargar por ciclo')
    return parser.parse_args()

def registrar_senal(activo, senal, precio, motivo, puntuacion, modo):
    """Guarda la señal en operaciones_ejecutadas"""
    try:
        data = {
            'activo': activo,
            'temporalidad': '1H',
            'senal': senal,
            'precio_entrada': precio,
            'motivo': motivo,
            'puntuacion_confluencia': puntuacion,
            'ejecutada': False,
            'timestamp': datetime.now().isoformat()
        }
        result = db.table('operaciones_ejecutadas').insert(data).execute()
        logger.info(f"📝 Señal registrada: {activo} | {senal} | ${precio} | {motivo}")
        return result
    except Exception as e:
        logger.error(f"❌ Error registrando señal: {e}")
        return None

def ejecutar_ciclo(exchange, activos, limite, modo):
    """Ejecuta un ciclo de trading: descarga → análisis → registro"""
    logger.info(f"🔄 Ciclo iniciado: {exchange} | {activos}")
    
    pipeline = PipelineVelas(exchange_id=exchange)
    resultados = []
    
    for activo in activos.split(','):
        activo = activo.strip()
        try:
            # 1. Descargar velas
            velas = pipeline.obtener_velas(activo, '1H', limite)
            if not velas:
                logger.warning(f"⚠️ No se obtuvieron velas para {activo}")
                continue
            
            # 2. Analizar
            trader = TradingLogic()
            senal = trader.analizar(velas, activo)
            logger.info(f"📊 {activo} -> {senal['senal']} | {senal['motivo']}")
            
            # 3. Registrar si es COMPRA o VENTA
            if senal['senal'] in ('COMPRA', 'VENTA'):
                registrar_senal(
                    activo=activo,
                    senal=senal['senal'],
                    precio=senal.get('precio_actual', velas[-1]['close']),
                    motivo=senal.get('motivo', ''),
                    puntuacion=senal.get('score', 0),
                    modo=modo
                )
            
            resultados.append(senal)
            
        except Exception as e:
            logger.error(f"❌ Error procesando {activo}: {e}")
            traceback.print_exc()
    
    return resultados

def main():
    args = parse_args()
    logger.info(f"🧠 Siegfried Trading Agent iniciado")
    logger.info(f"   Exchange: {args.exchange}")
    logger.info(f"   Activos: {args.activos}")
    logger.info(f"   Modo: {args.modo}")
    logger.info(f"   Intervalo: {args.intervalo}s")
    
    while True:
        try:
            ejecutar_ciclo(args.exchange, args.activos, args.limite, args.modo)
            
            if args.una_vez:
                logger.info("✅ Ciclo único completado. Saliendo.")
                break
            
            logger.info(f"⏳ Esperando {args.intervalo}s para próximo ciclo...")
            time.sleep(args.intervalo)
            
        except KeyboardInterrupt:
            logger.info("🛑 Interrupción recibida. Saliendo...")
            break
        except Exception as e:
            logger.error(f"❌ Error en ciclo principal: {e}")
            traceback.print_exc()
            time.sleep(10)

if __name__ == "__main__":
    main()
