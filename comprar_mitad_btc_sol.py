import os
import sys
from decimal import Decimal
from dotenv import load_dotenv
from binance.client import Client
from binance.exceptions import BinanceAPIException
from supabase import create_client, Client as SupabaseClient

load_dotenv()

API_KEY = os.getenv("BINANCE_API_KEY")
SECRET_KEY = os.getenv("BINANCE_SECRET_KEY")
if not API_KEY or not SECRET_KEY:
    print("❌ Faltan claves de Binance en .env")
    sys.exit(1)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
if not SUPABASE_URL or not SUPABASE_KEY:
    print("❌ Faltan claves de Supabase en .env")
    sys.exit(1)

client = Client(API_KEY, SECRET_KEY)
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def comprar_mitad(usdt_total=10):
    try:
        # Verificar saldo USDT
        balance = client.get_asset_balance(asset='USDT')
        disponible = float(balance['free'])
        if disponible < usdt_total:
            print(f"⚠️ Saldo insuficiente. Tienes {disponible:.2f} USDT, usando todo.")
            usdt_total = disponible

        mitad = usdt_total / 2

        # ===== BTC =====
        ticker_btc = client.get_symbol_ticker(symbol="BTCUSDT")
        precio_btc = float(ticker_btc['price'])
        print(f"💰 Precio BTC: ${precio_btc:.2f}")
        cantidad_btc = Decimal(mitad / precio_btc).quantize(Decimal('0.00000001'))
        cantidad_btc_str = f"{cantidad_btc:.8f}"  # -> "0.00003871"
        print(f"📦 Comprando {cantidad_btc_str} BTC por {mitad:.2f} USDT")

        orden_btc = client.order_market_buy(symbol="BTCUSDT", quantity=cantidad_btc_str)
        print("✅ Orden BTC ejecutada")

        data_btc = {
            "fecha": "2026-07-19",
            "activo": "BTC",
            "tipo": "BUY",
            "precio_entrada": precio_btc,
            "cantidad": float(cantidad_btc_str),
            "inversion_usd": mitad,
            "precio_actual": precio_btc,
            "valor_actual_usd": mitad,
            "ganancia_perdida": 0,
            "roi": 0,
            "estado": "ABIERTA"
        }
        supabase.table("agente_trade_real").insert(data_btc).execute()
        print("✅ Registro BTC guardado")

        # ===== SOL =====
        ticker_sol = client.get_symbol_ticker(symbol="SOLUSDT")
        precio_sol = float(ticker_sol['price'])
        print(f"💰 Precio SOL: ${precio_sol:.2f}")
        cantidad_sol = Decimal(mitad / precio_sol).quantize(Decimal('0.00000001'))
        cantidad_sol_str = f"{cantidad_sol:.8f}"
        print(f"📦 Comprando {cantidad_sol_str} SOL por {mitad:.2f} USDT")

        orden_sol = client.order_market_buy(symbol="SOLUSDT", quantity=cantidad_sol_str)
        print("✅ Orden SOL ejecutada")

        data_sol = {
            "fecha": "2026-07-19",
            "activo": "SOL",
            "tipo": "BUY",
            "precio_entrada": precio_sol,
            "cantidad": float(cantidad_sol_str),
            "inversion_usd": mitad,
            "precio_actual": precio_sol,
            "valor_actual_usd": mitad,
            "ganancia_perdida": 0,
            "roi": 0,
            "estado": "ABIERTA"
        }
        supabase.table("agente_trade_real").insert(data_sol).execute()
        print("✅ Registro SOL guardado")

        # Resumen
        balance_final = client.get_asset_balance(asset='USDT')
        print(f"\n✅ INVERSIÓN COMPLETADA")
        print(f"💵 Saldo USDT restante: {float(balance_final['free']):.2f}")
        print(f"📊 Total invertido: {usdt_total:.2f} USDT (50% BTC, 50% SOL)")

        return True
    except BinanceAPIException as e:
        print(f"❌ Error Binance: {e.message}")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    monto = float(input("¿Cuántos USDT invertir? (default 10): ") or 10)
    comprar_mitad(monto)
