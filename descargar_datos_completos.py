import ccxt
import pandas as pd
import os
import time

def descargar_todos_los_datos(symbol='BTC/USD', timeframe='1h', total_velas=8760):
    """Descarga velas paginando (Kraken limita a 720 por request)."""
    exchange = ccxt.kraken()
    all_ohlcv = []
    since = None
    
    while len(all_ohlcv) < total_velas:
        try:
            ohlcv = exchange.fetch_ohlcv(symbol, timeframe, since=since, limit=720)
            if not ohlcv:
                break
            all_ohlcv.extend(ohlcv)
            since = ohlcv[-1][0] + 1  # Siguiente vela después de la última
            print(f'Descargadas {len(all_ohlcv)} velas...')
            time.sleep(1)  # Evitar rate limit
        except Exception as e:
            print(f'⚠️ Error: {e}. Reintentando en 2 segundos...')
            time.sleep(2)
    
    df = pd.DataFrame(all_ohlcv, columns=['timestamp', 'Open', 'High', 'Low', 'Close', 'Volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df = df.set_index('timestamp')
    df = df[~df.index.duplicated(keep='last')]  # Eliminar duplicados
    return df

if __name__ == '__main__':
    print('📥 Descargando 1 año de velas (8760)...')
    df = descargar_todos_los_datos(symbol='BTC/USD', timeframe='1h', total_velas=8760)
    print(f'✅ {len(df)} velas descargadas')
    
    # Guardar en CSV
    output_path = os.path.expanduser('~/DepaFix_Maestro/datos_btc_1h.csv')
    df.to_csv(output_path)
    print(f'📁 Datos guardados en {output_path}')
