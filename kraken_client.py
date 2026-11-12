import os
import krakenex
from dotenv import load_dotenv

load_dotenv()

def get_kraken_client():
    api = krakenex.API(
        key=os.getenv('KRAKEN_API_KEY'),
        secret=os.getenv('KRAKEN_API_SECRET')
    )
    return api

def get_ticker(pair='XXBTZUSD'):
    api = get_kraken_client()
    response = api.query_public('Ticker', {'pair': pair})
    if 'result' in response:
        # Kraken devuelve el par con otro nombre, así que tomamos la primera clave
        key = list(response['result'].keys())[0]
        data = response['result'][key]
        return {
            'pair': key,
            'precio_actual': float(data['c'][0]),
            'precio_apertura': float(data['o']),
            'volumen_24h': float(data['v'][1]),
            'high_24h': float(data['h'][1]),
            'low_24h': float(data['l'][1])
        }
    return None

def get_balance():
    api = get_kraken_client()
    response = api.query_private('Balance')
    if 'result' in response:
        return response['result']
    return None

if __name__ == '__main__':
    print('🔍 Probando conexión a Kraken...')
    
    # Probar BTC/USD
    ticker = get_ticker('XXBTZUSD')
    if ticker:
        print(f'✅ {ticker["pair"]}: ${ticker["precio_actual"]:.2f}')
        print(f'   High 24h: ${ticker["high_24h"]:.2f}')
        print(f'   Low 24h: ${ticker["low_24h"]:.2f}')
        print(f'   Volumen 24h: {ticker["volumen_24h"]:.2f}')
    else:
        print('❌ Error al obtener el precio de BTC')
    
    # Probar ETH/USD
    eth = get_ticker('XETHZUSD')
    if eth:
        print(f'✅ {eth["pair"]}: ${eth["precio_actual"]:.2f}')
    
    # Probar saldo
    try:
        balance = get_balance()
        if balance:
            print(f'✅ Saldo disponible: {balance}')
        else:
            print('⚠️ No se pudo obtener el saldo (puede que falten permisos).')
    except Exception as e:
        print(f'⚠️ Saldo no disponible: {e}')
