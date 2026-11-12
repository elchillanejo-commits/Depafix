import os
import time
from datetime import datetime
from dotenv import load_dotenv
from kraken_client import get_ticker, get_balance

load_dotenv()

def mostrar_dashboard():
    """Muestra el precio actual de BTC, ETH y el saldo en Kraken."""
    print("\n" + "=" * 60)
    print(f"📊 DASHBOARD DE TRADING - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # Precio de BTC
    btc = get_ticker('XXBTZUSD')
    if btc:
        print(f"🟠 BTC/USD: ${btc['precio_actual']:,.2f}")
        print(f"   High 24h: ${btc['high_24h']:,.2f} | Low 24h: ${btc['low_24h']:,.2f}")
        print(f"   Volumen 24h: {btc['volumen_24h']:,.2f} BTC")
    
    # Precio de ETH
    eth = get_ticker('XETHZUSD')
    if eth:
        print(f"🔵 ETH/USD: ${eth['precio_actual']:,.2f}")
    
    # Saldo
    balance = get_balance()
    if balance:
        print("\n💰 SALDO:")
        for moneda, cantidad in balance.items():
            if float(cantidad) > 0:
                print(f"   {moneda}: {cantidad}")
    
    print("=" * 60)

def monitorear(intervalo=300, umbral_subida=None, umbral_bajada=None):
    """
    Monitorea el precio cada X segundos y avisa si cruza los umbrales.
    - intervalo: segundos entre cada consulta (default 300 = 5 min).
    - umbral_subida: si BTC sube de este precio, avisa.
    - umbral_bajada: si BTC baja de este precio, avisa.
    """
    print(f"🔍 Monitoreando BTC cada {intervalo} segundos...")
    if umbral_subida:
        print(f"   ⬆️ Avisar si BTC sube de ${umbral_subida:,.2f}")
    if umbral_bajada:
        print(f"   ⬇️ Avisar si BTC baja de ${umbral_bajada:,.2f}")
    print("   Presiona Ctrl+C para detener.\n")
    
    ultimo_precio = None
    while True:
        try:
            btc = get_ticker('XXBTZUSD')
            if btc:
                precio = btc['precio_actual']
                ahora = datetime.now().strftime('%H:%M:%S')
                
                # Mostrar cambio
                if ultimo_precio:
                    cambio = precio - ultimo_precio
                    simbolo = "📈" if cambio > 0 else "📉"
                    print(f"[{ahora}] BTC: ${precio:,.2f} {simbolo} ({cambio:+.2f})")
                else:
                    print(f"[{ahora}] BTC: ${precio:,.2f}")
                
                # Verificar umbrales
                if umbral_subida and precio >= umbral_subida:
                    print(f"\n🚨 ¡ALERTA! BTC superó ${umbral_subida:,.2f} (actual: ${precio:,.2f})")
                if umbral_bajada and precio <= umbral_bajada:
                    print(f"\n🚨 ¡ALERTA! BTC bajó de ${umbral_bajada:,.2f} (actual: ${precio:,.2f})")
                
                ultimo_precio = precio
            
            time.sleep(intervalo)
        except KeyboardInterrupt:
            print("\n⏹️ Monitoreo detenido.")
            break
        except Exception as e:
            print(f"⚠️ Error: {e}")
            time.sleep(intervalo)

if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == 'monitorear':
        # Modo monitoreo: python3 dashboard_trading.py monitorear [intervalo] [umbral_subida] [umbral_bajada]
        intervalo = int(sys.argv[2]) if len(sys.argv) > 2 else 300
        umbral_subida = float(sys.argv[3]) if len(sys.argv) > 3 else None
        umbral_bajada = float(sys.argv[4]) if len(sys.argv) > 4 else None
        monitorear(intervalo, umbral_subida, umbral_bajada)
    else:
        # Modo dashboard (una sola vez)
        mostrar_dashboard()
