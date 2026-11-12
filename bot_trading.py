import os
import sys
from dotenv import load_dotenv
from supabase import create_client
from openai import OpenAI
from kraken_client import get_ticker, get_balance
from backtesting import Backtest
from backtesting.lib import FractionalBacktest
from src.estrategias import EstrategiaEMARSI
import ccxt
import pandas as pd

load_dotenv()

supabase = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_KEY'))
openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

def backtest_rapido(symbol='BTC/USD', timeframe='1h', limit=500):
    """Corre un backtest rápido de las últimas 500 velas."""
    exchange = ccxt.kraken()
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
    df = pd.DataFrame(ohlcv, columns=['timestamp', 'Open', 'High', 'Low', 'Close', 'Volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df = df.set_index('timestamp')
    bt = FractionalBacktest(df, EstrategiaEMARSI, cash=1000, commission=0.001)
    stats = bt.run()
    return {
        'return_pct': stats['Return [%]'],
        'drawdown_pct': stats['Max. Drawdown [%]'],
        'sharpe': stats['Sharpe Ratio'],
        'trades': stats['# Trades']
    }

def consultar_bot(pregunta):
    ticker = get_ticker('XXBTZUSD')
    balance = get_balance()
    
    contexto_precio = ""
    if ticker:
        contexto_precio = f"""
PRECIO EN VIVO (Kraken):
- BTC/USD: ${ticker['precio_actual']:.2f}
- High 24h: ${ticker['high_24h']:.2f}
- Low 24h: ${ticker['low_24h']:.2f}
- Volumen 24h: {ticker['volumen_24h']:.2f} BTC
"""
    if balance:
        contexto_precio += f"\nSALDO ACTUAL: {balance}\n"
    
    # Backtest rápido
    try:
        metricas = backtest_rapido()
        contexto_backtest = f"""
MÉTRICAS DE BACKTEST (500 velas):
- Retorno: {metricas['return_pct']:.2f}%
- Drawdown: {metricas['drawdown_pct']:.2f}%
- Sharpe: {metricas['sharpe']:.2f}
- Trades: {metricas['trades']}
"""
    except Exception as e:
        contexto_backtest = f"\n⚠️ Backtest no disponible: {e}\n"
    
    response_emb = openai_client.embeddings.create(
        input=pregunta,
        model='text-embedding-3-small',
        dimensions=384
    )
    response = supabase.rpc('match_chunks', {
        'query_embedding': response_emb.data[0].embedding,
        'match_threshold': 0.3,
        'match_count': 5
    }).execute()
    contexto_rag = '\n\n'.join([row['content'] for row in response.data])
    
    prompt = f'''Eres un asesor financiero experto en criptomonedas. Usa este contexto para responder la pregunta del usuario.

CONTEXTO DE MERCADO EN VIVO:
{contexto_precio}

MÉTRICAS DE BACKTEST:
{contexto_backtest}

CONOCIMIENTO TÉCNICO (RAG):
{contexto_rag}

PREGUNTA DEL USUARIO:
{pregunta}

Responde de forma directa, práctica y con recomendaciones claras.'''
    
    respuesta = openai_client.chat.completions.create(
        model='gpt-4o-mini',
        messages=[{'role': 'user', 'content': prompt}],
        temperature=0.7
    )
    return respuesta.choices[0].message.content

if __name__ == '__main__':
    pregunta = ' '.join(sys.argv[1:]) if len(sys.argv) > 1 else '¿Qué estrategia me recomiendas para operar en Kraken?'
    print(consultar_bot(pregunta))
