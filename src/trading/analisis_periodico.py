#!/usr/bin/env python3
"""
Análisis periódico quincenal y mensual de BTC y SOL.
Calcula RSI/EMA reales, evalúa confluencia y guarda en memoria_trading.
"""
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from datetime import datetime, timedelta
from supabase import create_client
from dotenv import load_dotenv
import pandas as pd
import numpy as np

load_dotenv()
db = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_KEY'))

# ========== FUNCIONES DE ANÁLISIS ==========

def calcular_rsi(close, period=14):
    """Calcula RSI real sobre una serie de precios."""
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def calcular_ema(close, period=50):
    """Calcula EMA real (exponencial)."""
    return close.ewm(span=period, adjust=False).mean()

def evaluar_senal(row, df_velas):
    """Evalúa una señal contra velas históricas (sin look-ahead)."""
    timestamp = row['timestamp']
    velas = df_velas[df_velas['tiempo'] <= timestamp].copy()
    if len(velas) < 50:
        return None, None
    
    velas['rsi'] = calcular_rsi(velas['cierre'])
    velas['ema50'] = calcular_ema(velas['cierre'])
    
    precio = row['precio_entrada']
    factores = []
    
    min_20 = velas['minimo'].tail(20).min()
    if abs(precio - min_20) / precio < 0.005:
        factores.append('soporte_estatico')
    
    max_impulso = velas['maximo'].tail(50).max()
    min_impulso = velas['minimo'].tail(50).min()
    fib_618 = min_impulso + 0.618 * (max_impulso - min_impulso)
    fib_786 = min_impulso + 0.786 * (max_impulso - min_impulso)
    if fib_618 <= precio <= fib_786:
        factores.append('golden_pocket')
    
    ema_actual = velas['ema50'].iloc[-1]
    if abs(precio - ema_actual) / precio < 0.005:
        factores.append('ema50')
    
    rsi_actual = velas['rsi'].iloc[-1]
    if rsi_actual < 30:
        factores.append('rsi_sobreventa')
    elif rsi_actual > 70:
        factores.append('rsi_sobrecompra')
    
    return len(factores), factores

def generar_reporte_quincenal():
    print("📊 Generando reporte quincenal...")
    hoy = datetime.now()
    inicio = hoy - timedelta(days=15)
    data = db.table('operaciones_ejecutadas').select('*').gte('timestamp', inicio.isoformat()).execute()
    if not data.data:
        print("⚠️ No hay datos en el período quincenal.")
        return
    df = pd.DataFrame(data.data)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    total = len(df)
    compras = len(df[df['senal'] == 'COMPRA'])
    ventas = len(df[df['senal'] == 'VENTA'])
    esperas = len(df[df['senal'] == 'ESPERA'])
    alta_confluencia = len(df[df['puntuacion_confluencia'] >= 3])
    
    resumen = {
        'total_senales': total,
        'compras': compras,
        'ventas': ventas,
        'esperas': esperas,
        'alta_confluencia': alta_confluencia,
        'pct_compra': compras/total*100 if total>0 else 0,
        'pct_venta': ventas/total*100 if total>0 else 0,
        'pct_espera': esperas/total*100 if total>0 else 0,
        'periodo': f"{inicio.strftime('%Y-%m-%d')}_a_{hoy.strftime('%Y-%m-%d')}"
    }
    db.table('reportes_trading').insert({
        'tipo': 'quincenal',
        'periodo': resumen['periodo'],
        'resumen': resumen,
        'detalle': df.to_dict(orient='records')[:100],
        'tendencias': {'tendencia_principal': 'alcista' if compras > ventas else 'bajista'}
    }).execute()
    print(f"✅ Reporte quincenal guardado. {total} señales, {compras} COMPRA, {ventas} VENTA.")

def generar_reporte_mensual():
    print("📊 Generando reporte mensual...")
    hoy = datetime.now()
    inicio = hoy - timedelta(days=30)
    data = db.table('operaciones_ejecutadas').select('*').gte('timestamp', inicio.isoformat()).execute()
    if not data.data:
        print("⚠️ No hay datos en el período mensual.")
        return
    df = pd.DataFrame(data.data)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    total = len(df)
    compras = len(df[df['senal'] == 'COMPRA'])
    ventas = len(df[df['senal'] == 'VENTA'])
    esperas = len(df[df['senal'] == 'ESPERA'])
    alta_confluencia = len(df[df['puntuacion_confluencia'] >= 3])
    resumen = {
        'total_senales': total,
        'compras': compras,
        'ventas': ventas,
        'esperas': esperas,
        'alta_confluencia': alta_confluencia,
        'pct_compra': compras/total*100 if total>0 else 0,
        'pct_venta': ventas/total*100 if total>0 else 0,
        'pct_espera': esperas/total*100 if total>0 else 0,
        'periodo': f"{inicio.strftime('%Y-%m-%d')}_a_{hoy.strftime('%Y-%m-%d')}"
    }
    db.table('reportes_trading').insert({
        'tipo': 'mensual',
        'periodo': resumen['periodo'],
        'resumen': resumen,
        'detalle': df.to_dict(orient='records')[:100],
        'tendencias': {'tendencia_principal': 'alcista' if compras > ventas else 'bajista'}
    }).execute()
    print(f"✅ Reporte mensual guardado. {total} señales, {compras} COMPRA, {ventas} VENTA.")

def mostrar_resumen():
    data = db.table('reportes_trading').select('*').order('created_at', desc=True).limit(1).execute()
    if data.data:
        row = data.data[0]
        print(f"📊 Último reporte ({row['tipo']}):")
        print(f"  Período: {row['periodo']}")
        print(f"  Total señales: {row['resumen']['total_senales']}")
        print(f"  COMPRA: {row['resumen']['compras']} ({row['resumen']['pct_compra']:.1f}%)")
        print(f"  VENTA: {row['resumen']['ventas']} ({row['resumen']['pct_venta']:.1f}%)")
        print(f"  ESPERA: {row['resumen']['esperas']} ({row['resumen']['pct_espera']:.1f}%)")
        print(f"  Alta confluencia (≥3/4): {row['resumen']['alta_confluencia']}")
    else:
        print("⚠️ No hay reportes guardados aún.")

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--quincenal', action='store_true')
    parser.add_argument('--mensual', action='store_true')
    parser.add_argument('--resumen', action='store_true')
    args = parser.parse_args()
    if args.quincenal:
        generar_reporte_quincenal()
    elif args.mensual:
        generar_reporte_mensual()
    elif args.resumen:
        mostrar_resumen()
    else:
        print("⚠️ Usa --quincenal, --mensual o --resumen")
