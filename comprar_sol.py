import os
import sys
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

def comprar_sol(usdt_amount=10):
    try:
        ticker = client.get_symbol_ticker(symbol="SOLUSDT")
        precio = float(ticker['price'])
        print(f"💰 Precio SOL/USDT: ${precio:.2f}")

        cantidad = round(usdt_amount / precio, 8)
        print(f"📦 Comprando {cantidad} SOL por {usdt_amount} USDT")

        orden = client.order_market_buy(symbol="SOLUSDT", quantity=cantidad)
        print("✅ Orden ejecutada:", orden)

        data = {
            "fecha": "2026-07-19",
            "activo": "SOL",
            "tipo": "BUY",
            "precio_entrada": precio,
            "cantidad": cantidad,
            "inversion_usd": usdt_amount,
            "precio_actual": precio,
            "valor_actual_usd": usdt_amount,
            "ganancia_perdida": 0,
            "roi": 0,
            "estado": "ABIERTA"
        }
        result = supabase.table("agente_trade_real").insert(data).execute()
        print("✅ Registro guardado en Supabase")

        balance = client.get_asset_balance(asset='USDT')
        print(f"💵 Saldo USDT restante: {float(balance['free']):.2f}")
        return True
    except BinanceAPIException as e:
        print(f"❌ Error Binance: {e.message}")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    monto = float(input("¿Cuántos USDT invertir? (default 10): ") or 10)
    comprar_sol(monto)
