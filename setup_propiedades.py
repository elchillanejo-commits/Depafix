import os
import pandas as pd
import math
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()
supabase = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_KEY'))
EXCEL_PATH = "/home/ibar/Descargas/propiedades_11_2026.xlsx"

def limpiar(val):
    if pd.isna(val) or val is None: return None
    if isinstance(val, float) and (math.isnan(val) or math.isinf(val)): return None
    return str(val).strip() if isinstance(val, str) else val

print("⏳ Leyendo Excel...")
df = pd.read_excel(EXCEL_PATH, sheet_name='Propiedades', header=0)
registros = []

for idx, row in df.iterrows():
    if pd.isna(row.iloc[0]) or pd.isna(row.iloc[1]): continue
    try:
        registros.append({
            'id': int(row.iloc[0]),
            'direccion': str(row.iloc[1]).strip(),
            'comuna': limpiar(row.iloc[3]),
            'tipo': limpiar(row.iloc[9]),
            'estado': limpiar(row.iloc[18]),
            'valor_arriendo': float(row.iloc[21]) if not pd.isna(row.iloc[21]) else 0.0,
            'arrendatario_nombre': limpiar(row.iloc[10])
        })
    except Exception as e:
        print(f"⚠️ Error fila {idx}: {e}")

print(f"✅ {len(registros)} propiedades listas. Subiendo en lotes...")

# Subida en lotes de 50 para evitar timeouts o errores de JSON
for i in range(0, len(registros), 50):
    lote = registros[i:i+50]
    try:
        supabase.table('propiedades_v1').upsert(lote).execute()
        print(f"   -> Lote {i//50 + 1} OK ({len(lote)} registros)")
    except Exception as e:
        print(f"❌ Error en lote {i//50 + 1}: {e}")

print("✅ Proceso finalizado.")
