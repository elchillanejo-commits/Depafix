import pandas as pd
import numpy as np

def calcular_soportes_resistencias(velas, ventana=20):
    """Encuentra soportes y resistencias basados en máximos/mínimos."""
    if len(velas) < ventana:
        return [], []
    df = pd.DataFrame(velas)
    df['high_rolling'] = df['high'].rolling(window=ventana, center=True).max()
    df['low_rolling'] = df['low'].rolling(window=ventana, center=True).min()
    
    # Resistencia: máximos locales
    resistencias = df[df['high'] == df['high_rolling']]['high'].values.tolist()
    # Soporte: mínimos locales
    soportes = df[df['low'] == df['low_rolling']]['low'].values.tolist()
    
    # Limpiar duplicados cercanos (dentro del 0.5%)
    def limpiar_niveles(niveles):
        niveles_ordenados = sorted(niveles)
        niveles_limpios = []
        for n in niveles_ordenados:
            if not niveles_limpios or abs(n - niveles_limpios[-1]) / n > 0.005:
                niveles_limpios.append(n)
        return niveles_limpios
    
    return limpiar_niveles(soportes), limpiar_niveles(resistencias)

def detectar_fvg(velas):
    """Detecta Fair Value Gaps (FVG) en las velas."""
    if len(velas) < 3:
        return []
    fvgs = []
    for i in range(2, len(velas)):
        vela1 = velas[i-2]
        vela2 = velas[i-1]
        vela3 = velas[i]
        # FVG bajista (gap entre vela1 y vela3)
        if vela1['low'] > vela3['high']:
            fvgs.append({
                'tipo': 'bajista',
                'superior': vela1['low'],
                'inferior': vela3['high'],
                'tiempo': vela2['tiempo']
            })
        # FVG alcista (gap entre vela3 y vela1)
        elif vela1['high'] < vela3['low']:
            fvgs.append({
                'tipo': 'alcista',
                'inferior': vela1['high'],
                'superior': vela3['low'],
                'tiempo': vela2['tiempo']
            })
    return fvgs
