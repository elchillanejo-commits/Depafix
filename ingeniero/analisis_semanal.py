#!/usr/bin/env python3
"""
analisis_semanal.py — Informe cuantitativo ejecutivo para DepaFix.
Audita señales, factores y win rate hipotético basado en datos de Supabase.
"""
import os
import sys
import json
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from supabase import create_client

# Configuración y Rutas
BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = Path.home() / "PROYECTOS/Proyectos/DepaFix/.env"
LOG_DIR = BASE_DIR / "ingeniero/logs"
HILO_PATH = Path.home() / "Documentos/HILO_CONDUCTOR.txt"

load_dotenv(ENV_PATH)

def get_supabase():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise ValueError("Supabase credenciales faltantes")
    return create_client(url, key)

def fetch_data(client):
    try:
        # Extraer últimos 7 días
        dias_atras = datetime.now(timezone.utc) - timedelta(days=7)
        ops = client.table("operaciones_ejecutadas").select("*").gte("timestamp", dias_atras.isoformat()).execute()
        velas = client.table("velas_cripto").select("par,cierre").order("tiempo", desc=True).limit(100).execute()
        return pd.DataFrame(ops.data), pd.DataFrame(velas.data)
    except Exception as e:
        print(f"Error extrayendo datos: {e}")
        return None, None

def analizar_factores(df):
    df['confluencia_detalle'] = df['confluencia_detalle'].apply(lambda x: x if isinstance(x, list) else [])
    factores = ["EMA50", "RSI", "Golden Pocket", "FVG", "OB"]
    resultados = {}
    for f in factores:
        resultados[f] = df['confluencia_detalle'].apply(lambda x: any(f in str(i) for i in x)).sum()
    return resultados

def calcular_win_rate(df, velas_df):
    precios_actuales = velas_df.groupby('par')['cierre'].last().to_dict()
    def evaluar(row):
        precio_actual = precios_actuales.get(row['activo'])
        if not precio_actual or pd.isna(row['precio_entrada']): return None
        if row['senal'] == 'COMPRA': return precio_actual > row['precio_entrada']
        if row['senal'] == 'VENTA': return precio_actual < row['precio_entrada']
        return None
    
    df['win'] = df.apply(evaluar, axis=1)
    return df[df['senal'].isin(['COMPRA', 'VENTA'])]['win'].mean()

def generar_informe(df, velas_df):
    # A. Distribución
    dist_senal = df['senal'].value_counts().to_dict()
    dist_activo = df['activo'].value_counts().to_dict()
    
    # B. Factores
    factores = analizar_factores(df)
    
    # C. Win Rate
    win_rate = calcular_win_rate(df, velas_df)
    
    # D. Riesgo/Beneficio
    df['rb_ratio'] = (df['take_profit_1'] - df['precio_entrada']).abs() / (df['precio_entrada'] - df['stop_loss']).abs()
    rb_prom = df['rb_ratio'].mean()

    informe = f"""
## 📊 INFORME CUANTITATIVO SEMANAL — {datetime.now().strftime('%Y-%m-%d')}

### A. Distribución de señales
- COMPRA: {dist_senal.get('COMPRA', 0)} | VENTA: {dist_senal.get('VENTA', 0)} | ESPERA: {dist_senal.get('ESPERA', 0)}
- Activos: {json.dumps(dist_activo)}

### B. Análisis de factores
{json.dumps(factores, indent=2)}

### C. Métricas de Rendimiento
- Win Rate Hipotético: {win_rate*100:.2f}%
- Ratio R/B Promedio: {rb_prom:.2f}

### D. Recomendaciones Automáticas
- {"Sugerir ajustar SCORE_MINIMO" if (dist_senal.get('COMPRA',0)+dist_senal.get('VENTA',0)) < dist_senal.get('ESPERA',0) else "Distribución balanceada"}
"""
    return informe

def main():
    try:
        client = get_supabase()
        df, velas_df = fetch_data(client)
        if df is None: return
        
        informe = generar_informe(df, velas_df)
        
        # Guardar archivo
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        filename = LOG_DIR / f"analisis_semanal_{datetime.now().strftime('%Y%m%d')}.md"
        with open(filename, "w") as f: f.write(informe)
        
        # Stdout
        print(informe)
        
        # HILO
        if HILO_PATH.exists():
            with open(HILO_PATH, "a") as f:
                f.write(f"\n--- Resumen semanal {datetime.now().strftime('%Y-%m-%d')} ---\n{informe[:300]}\n")
                
    except Exception as e:
        print(f"Error crítico en reporte: {e}")

if __name__ == "__main__":
    main()
