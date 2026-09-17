import os, sys
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
sys.path.insert(0, "05_TRADE_CRIPTO")
load_dotenv()

from supabase import create_client

URL = os.getenv("SUPABASE_URL")
KEY = os.getenv("SUPABASE_KEY")
client = create_client(URL, KEY)

since = (datetime.now(timezone.utc) - timedelta(days=16)).isoformat()

print("=" * 60)
print("📊 INFORME DEPAFIX BOT")
print("=" * 60)
print(f"Periodo: ultimos 16 dias (desde {since[:10]})")
print(f"Generado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 60)

# Velas
r = client.table("ohlcv").select("pair", count="exact").gte("timestamp", since).execute()
velas = r.count if hasattr(r, 'count') else len(r.data or [])
print(f"\n🗄️  Velas OHLCV guardadas: {velas}")

# Indicadores
r = client.table("indicators").select("id", count="exact").gte("timestamp", since).execute()
inds = r.count if hasattr(r, 'count') else len(r.data or [])
print(f"📈 Indicadores calculados: {inds}")

# Señales
r = client.table("signals").select("signal_type").gte("timestamp", since).execute()
tipos = {}
for row in (r.data or []):
    t = row.get("signal_type", "HOLD")
    tipos[t] = tipos.get(t, 0) + 1
print(f"\n📡 Senales generadas: {sum(tipos.values())}")
for t, c in tipos.items():
    print(f"   - {t}: {c}")

# Trades
r = client.table("trades").select("*").execute()
trades = r.data or []
abiertos = [t for t in trades if t.get("status") == "OPEN"]
cerrados = [t for t in trades if t.get("status") == "CLOSED"]
pnls = [t.get("pnl") or 0 for t in cerrados]
total_pnl = sum(pnls)

print(f"\n💰 Trades:")
print(f"   Abiertos: {len(abiertos)}")
print(f"   Cerrados: {len(cerrados)}")
print(f"   P&L Total: ${total_pnl:.2f}")
if cerrados:
    ganados = sum(1 for p in pnls if p > 0)
    win_rate = ganados / len(cerrados) * 100
    print(f"   Win Rate: {win_rate:.1f}% ({ganados}/{len(cerrados)})")

# Errores
r = client.table("bot_logs").select("*").gte("created_at", since).eq("level", "ERROR").limit(5).execute()
errores = r.data or []
print(f"\n⚠️  Errores recientes: {len(errores)}")
for e in errores[:3]:
    print(f"   [{e.get('created_at','')[:19]}] {e.get('component','?')}: {e.get('message','')[:60]}")

print("\n" + "=" * 60)
print(f"Modo: {'PAPER TRADING (simulacion)' if os.getenv('PAPER_TRADING','True')=='True' else 'REAL'}")
print("=" * 60)
