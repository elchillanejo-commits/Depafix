#!/usr/bin/env python3
from binance.client import Client
from datetime import datetime
from dotenv import load_dotenv
from src.db.database_manager import DatabaseManager
import os

load_dotenv()
client = Client(os.getenv('BINANCE_API_KEY'), os.getenv('BINANCE_SECRET_KEY'))
db = DatabaseManager().get_service_client()

SYMBOL = 'BTCUSDT'
INTERVAL = Client.KLINE_INTERVAL_1HOUR
DAYS_BACK = 30

def populate():
    klines = client.get_historical_klines(SYMBOL, INTERVAL, str(DAYS_BACK) + ' days ago UTC')
    for k in klines:
        data = {
            'par': 'BTC/USDT',
            'temporalidad': '1h',
            'tiempo': datetime.fromtimestamp(k[0]/1000).isoformat(),
            'apertura': k[1],
            'maximo': k[2],
            'minimo': k[3],
            'cierre': k[4],
            'volumen': k[5]
        }
        db.table('velas_cripto').upsert(data, on_conflict='par,temporalidad,tiempo').execute()
    print(f"Insertadas {len(klines)} velas")

if __name__ == '__main__':
    populate()
