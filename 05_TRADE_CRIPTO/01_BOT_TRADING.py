#!/usr/bin/env python3
"""
Bot de trading autónomo con cruce de medias (5/20) para Binance.
Usa Supabase directamente (sin depender de src/).
Registra velas en velas_cripto y señales en operaciones_ejecutadas.
"""
import os
import sys
import argparse
import logging
import time
from datetime import datetime, timedelta
from decimal import Decimal
import pandas as pd
from dotenv import load_dotenv
from binance.client import Client
from binance.exceptions import BinanceAPIException
from supabase import create_client, Client as SupabaseClient

# ========== CONFIGURACIÓN ==========
SYMBOL = 'BTCUSDT'
INTERVAL = Client.KLINE_INTERVAL_1HOUR
SHORT_MA = 5
LONG_MA = 20
TRADE_AMOUNT_USDT = Decimal('5.00')
MIN_ORDER_USDT = Decimal('10.0')
TEMPORALIDAD = '1h'

# ========== LOGGING ==========
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ========== DECORADOR DE REINTENTOS (simplificado) ==========
def red_segura(max_retries=3, delay=2):
    def decorator(func):
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    logger.warning(f"Intento {attempt+1}/{max_retries} falló: {e}")
                    if attempt == max_retries - 1:
                        raise
                    time.sleep(delay)
            return None
        return wrapper
    return decorator

# ========== CLASE PRINCIPAL ==========
class TradingBot:
    def __init__(self, dry_run=True):
        load_dotenv()
        self.dry_run = dry_run
        
        # Binance
        self.api_key = os.getenv('BINANCE_API_KEY')
        self.secret_key = os.getenv('BINANCE_SECRET_KEY')
        if not self.api_key or not self.secret_key:
            raise ValueError("Faltan BINANCE_API_KEY o BINANCE_SECRET_KEY en .env")
        self.client = Client(self.api_key, self.secret_key)
        
        # Supabase
        self.supabase_url = os.getenv('SUPABASE_URL')
        self.supabase_key = os.getenv('SUPABASE_KEY')
        if not self.supabase_url or not self.supabase_key:
            raise ValueError("Faltan SUPABASE_URL o SUPABASE_KEY en .env")
        self.db: SupabaseClient = create_client(self.supabase_url, self.supabase_key)

    def get_klines(self, limit=100):
        """Obtiene velas de Binance y las guarda en velas_cripto."""
        try:
            klines = self.client.get_klines(symbol=SYMBOL, interval=INTERVAL, limit=limit)
            df = pd.DataFrame(klines, columns=[
                'timestamp', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'quote_asset_volume', 'number_of_trades',
                'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
            ])
            df['close'] = df['close'].astype(float)
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            
            # Guardar en Supabase (evitar duplicados)
            for _, row in df.iterrows():
                data = {
                    'par': 'BTC/USDT',
                    'temporalidad': TEMPORALIDAD,
                    'tiempo': row['timestamp'].isoformat(),
                    'apertura': row['open'],
                    'maximo': row['high'],
                    'minimo': row['low'],
                    'cierre': row['close'],
                    'volumen': row['volume']
                }
                self.db.table('velas_cripto').upsert(data, on_conflict='par,temporalidad,tiempo').execute()
            logger.info(f"Guardadas {len(df)} velas en velas_cripto")
            return df
        except BinanceAPIException as e:
            logger.error(f"Error al obtener velas: {e}")
            return None

    def calculate_signal(self, df):
        """Calcula señal basada en cruce de medias móviles."""
        if df is None or len(df) < LONG_MA:
            return None, None
        df['ma_short'] = df['close'].rolling(SHORT_MA).mean()
        df['ma_long'] = df['close'].rolling(LONG_MA).mean()
        last = df.iloc[-1]
        prev = df.iloc[-2]
        if prev['ma_short'] <= prev['ma_long'] and last['ma_short'] > last['ma_long']:
            return 'COMPRA', f"Cruce alcista (MA5={last['ma_short']:.2f} > MA20={last['ma_long']:.2f})"
        elif prev['ma_short'] >= prev['ma_long'] and last['ma_short'] < last['ma_long']:
            return 'VENTA', f"Cruce bajista (MA5={last['ma_short']:.2f} < MA20={last['ma_long']:.2f})"
        else:
            return 'ESPERA', "Sin cruce"

    @red_segura(max_retries=3, delay=2)
    def place_order(self, side, quantity, price=None):
        """Ejecuta orden en Binance (o simula si dry_run)."""
        if self.dry_run:
            logger.info(f"[DRY-RUN] {side} {quantity} BTC a precio {price or 'MERCADO'}")
            return {'orderId': 'DRY_RUN', 'status': 'FILLED'}
        try:
            if side == 'BUY':
                order = self.client.order_market_buy(symbol=SYMBOL, quantity=quantity)
            else:
                order = self.client.order_market_sell(symbol=SYMBOL, quantity=quantity)
            logger.info(f"Orden ejecutada: {order}")
            return order
        except BinanceAPIException as e:
            logger.error(f"Error al ejecutar orden: {e}")
            raise

    def get_balance(self, asset='BTC'):
        if self.dry_run:
            return Decimal('0.001')
        balance = self.client.get_asset_balance(asset=asset)
        return Decimal(balance['free'])

    def get_usdt_balance(self):
        if self.dry_run:
            return Decimal('10.0')
        balance = self.client.get_asset_balance(asset='USDT')
        return Decimal(balance['free'])

    def log_signal(self, senal, precio, cantidad=None, motivo=None, ejecutada=False):
        """Registra la señal/operación en operaciones_ejecutadas."""
        data = {
            'activo': 'BTC/USDT',
            'temporalidad': TEMPORALIDAD,
            'senal': senal,
            'precio_entrada': float(precio) if precio else None,
            'precio_salida': None,
            'cantidad': float(cantidad) if cantidad else None,
            'motivo': motivo,
            'puntuacion_confluencia': None,
            'ejecutada': ejecutada,
            'timestamp': datetime.utcnow().isoformat()
        }
        try:
            self.db.table('operaciones_ejecutadas').insert(data).execute()
            logger.info(f"Registrada señal en operaciones_ejecutadas: {senal}")
        except Exception as e:
            logger.error(f"Error al registrar señal: {e}")

    def run(self):
        logger.info(f"Modo {'DRY-RUN' if self.dry_run else 'LIVE'}")
        df = self.get_klines(limit=100)
        if df is None:
            return
        current_price = Decimal(df.iloc[-1]['close'])
        senal, motivo = self.calculate_signal(df)
        logger.info(f"Señal: {senal} - {motivo}")
        self.log_signal(senal, current_price, motivo=motivo, ejecutada=False)

        if senal == 'ESPERA':
            return

        usdt = self.get_usdt_balance()
        btc = self.get_balance('BTC')
        logger.info(f"Saldo USDT: {usdt} | BTC: {btc}")

        if senal == 'COMPRA':
            if usdt < TRADE_AMOUNT_USDT:
                logger.warning(f"Saldo insuficiente: {usdt} USDT < {TRADE_AMOUNT_USDT}")
                return
            quantity = (TRADE_AMOUNT_USDT / current_price).quantize(Decimal('0.000001'))
            if quantity * current_price < MIN_ORDER_USDT:
                logger.warning(f"Cantidad muy pequeña: {quantity} BTC (< {MIN_ORDER_USDT} USDT)")
                return
            order = self.place_order('BUY', quantity, current_price)
            if order and order.get('status') == 'FILLED':
                self.log_signal('COMPRA', current_price, quantity, motivo + ' (EJECUTADA)', ejecutada=True)
            else:
                self.log_signal('COMPRA', current_price, quantity, motivo + ' (FALLIDA)', ejecutada=False)
        elif senal == 'VENTA':
            if btc <= 0:
                logger.warning("No hay BTC para vender")
                return
            quantity = btc.quantize(Decimal('0.000001'))
            order = self.place_order('SELL', quantity, current_price)
            if order and order.get('status') == 'FILLED':
                self.log_signal('VENTA', current_price, quantity, motivo + ' (EJECUTADA)', ejecutada=True)
            else:
                self.log_signal('VENTA', current_price, quantity, motivo + ' (FALLIDA)', ejecutada=False)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true', default=True)
    parser.add_argument('--live', action='store_true')
    args = parser.parse_args()
    dry_run = not args.live if args.live else args.dry_run
    bot = TradingBot(dry_run=dry_run)
    bot.run()

if __name__ == '__main__':
    main()
