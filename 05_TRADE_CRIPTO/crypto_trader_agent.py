#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
crypto_trader_agent.py - Agente de trading con análisis profesional:
- Soportes/Resistencias dinámicos
- Fibonacci (0.618, 0.786, Golden Pocket)
- Fair Value Gaps (FVG)
- Order Blocks (giros en V)
- Confluencia de múltiples factores para señales de alta probabilidad
"""

import sys
from pathlib import Path
import numpy as np
import logging
from typing import List, Dict, Any, Tuple

# "/home/ibar/Proyectos/02_PROCURADOR" (el path viejo de aca) no existe desde
# que ese directorio se renombro a DepaFix/procurador (commit 10462fe) -- en
# la practica nunca hizo falta porque trading_orchestrator.py, el unico
# entry point real, ya deja el core/ correcto en sys.path antes de importar
# este modulo. Se corrige igual para no dejar una ruta muerta si este modulo
# se llega a usar standalone.
_CORE_PATH = str(Path(__file__).resolve().parent.parent / "procurador")
if _CORE_PATH not in sys.path:
    sys.path.insert(0, _CORE_PATH)

logger = logging.getLogger(__name__)

# ========== CONFIGURACIÓN ==========
GOLDEN_POCKET = (0.618, 0.786)  # Fibonacci niveles clave
UMBRAL_SOPORTE = 0.02           # 2% de tolerancia
VENTANA_SOPORTE = 20            # velas para detectar soportes/resistencias
UMBRAL_CONFLUENCIA = 4          # factores mínimos (de 6) para disparar COMPRA/VENTA
PERIODO_EMA = 50
PERIODO_RSI = 14

# ========== FUNCIONES AUXILIARES ==========

def calcular_fibonacci(high: float, low: float) -> Dict[str, float]:
    """Calcula los niveles de Fibonacci para un movimiento."""
    diff = high - low
    return {
        '0.0': low,
        '0.236': low + diff * 0.236,
        '0.382': low + diff * 0.382,
        '0.5': low + diff * 0.5,
        '0.618': low + diff * 0.618,
        '0.786': low + diff * 0.786,
        '1.0': high
    }

def detectar_soportes_resistencias(velas: List[Dict], ventana: int = VENTANA_SOPORTE) -> Tuple[List[float], List[float]]:
    """Detecta soportes y resistencias usando mínimos/máximos locales."""
    if len(velas) < ventana:
        return [], []
    
    highs = np.array([v['high'] for v in velas])
    lows = np.array([v['low'] for v in velas])
    
    # Mínimos locales (soportes)
    soportes = []
    for i in range(ventana, len(lows)-ventana):
        if lows[i] == min(lows[i-ventana:i+ventana+1]):
            soportes.append(lows[i])
    
    # Máximos locales (resistencias)
    resistencias = []
    for i in range(ventana, len(highs)-ventana):
        if highs[i] == max(highs[i-ventana:i+ventana+1]):
            resistencias.append(highs[i])
    
    # Limpiar duplicados cercanos (dentro del 0.5%)
    def limpiar_niveles(niveles):
        if not niveles:
            return []
        niveles_ordenados = sorted(niveles)
        niveles_limpios = [niveles_ordenados[0]]
        for n in niveles_ordenados[1:]:
            if abs(n - niveles_limpios[-1]) / n > 0.005:
                niveles_limpios.append(n)
        return niveles_limpios
    
    return limpiar_niveles(soportes), limpiar_niveles(resistencias)

def detectar_fvg(velas: List[Dict]) -> List[Dict]:
    """Detecta Fair Value Gaps (FVG) en tres velas consecutivas."""
    if len(velas) < 3:
        return []
    fvgs = []
    for i in range(2, len(velas)):
        v1 = velas[i-2]
        v2 = velas[i-1]
        v3 = velas[i]
        # FVG bajista (gap entre v1 y v3)
        if v1['low'] > v3['high']:
            fvgs.append({
                'tipo': 'bajista',
                'superior': v1['low'],
                'inferior': v3['high'],
                'tiempo': v2['tiempo'],
                'mitigado': False  # se actualiza después
            })
        # FVG alcista (gap entre v3 y v1)
        elif v1['high'] < v3['low']:
            fvgs.append({
                'tipo': 'alcista',
                'inferior': v1['high'],
                'superior': v3['low'],
                'tiempo': v2['tiempo'],
                'mitigado': False
            })
    return fvgs

def detectar_order_blocks(velas: List[Dict]) -> List[Dict]:
    """Detecta Order Blocks (giros en V) en los extremos."""
    if len(velas) < 5:
        return []
    blocks = []
    for i in range(2, len(velas)-2):
        # V invertida (pico) = resistencia
        if velas[i-2]['high'] < velas[i]['high'] > velas[i+2]['high']:
            blocks.append({
                'tipo': 'resistencia',
                'precio': velas[i]['high'],
                'tiempo': velas[i]['tiempo']
            })
        # V (valle) = soporte
        elif velas[i-2]['low'] > velas[i]['low'] < velas[i+2]['low']:
            blocks.append({
                'tipo': 'soporte',
                'precio': velas[i]['low'],
                'tiempo': velas[i]['tiempo']
            })
    return blocks

def calcular_ema(velas: List[Dict], periodo: int = 50) -> float:
    """Calcula la EMA (media móvil exponencial) de cierre sobre las últimas
    `periodo` velas, con suavizado estándar alpha = 2/(periodo+1)."""
    if len(velas) < periodo:
        return 0.0
    closes = np.array([v['close'] for v in velas[-periodo:]])
    alpha = 2.0 / (periodo + 1)
    ema = closes[0]
    for precio in closes[1:]:
        ema = alpha * precio + (1 - alpha) * ema
    return float(ema)

def calcular_rsi(velas: List[Dict], periodo: int = 14) -> float:
    """Calcula el RSI (Relative Strength Index) de cierre sobre las últimas
    `periodo` velas. Sin suficientes velas devuelve 50.0 (neutral) en vez de
    lanzar, para no romper la confluencia por falta de historial."""
    if len(velas) < periodo + 1:
        return 50.0
    closes = np.array([v['close'] for v in velas[-(periodo + 1):]])
    deltas = np.diff(closes)
    ganancias = np.where(deltas > 0, deltas, 0.0)
    perdidas = np.where(deltas < 0, -deltas, 0.0)
    ganancia_media = np.mean(ganancias)
    perdida_media = np.mean(perdidas)
    if perdida_media == 0:
        return 100.0
    rs = ganancia_media / perdida_media
    return float(100 - (100 / (1 + rs)))

def generar_senal(velas: List[Dict]) -> Dict[str, Any]:
    """
    Genera señal de trading basada en confluencia de factores:
    - Precio cerca de soporte/resistencia + FVG + Order Block = ALTA PROBABILIDAD
    - Precio en Golden Pocket = SEÑAL DE ENTRADA
    - EMA-50 (tendencia) y RSI-14 (sobrecompra/sobreventa) confirman la dirección
    """
    if len(velas) < 50:
        return {'senal': 'ESPERA', 'motivo': 'Datos insuficientes'}
    
    # Obtener datos actuales
    precio_actual = velas[-1]['close']
    high_max = max(v['high'] for v in velas[-50:])
    low_min = min(v['low'] for v in velas[-50:])
    
    # 1. Fibonacci
    fib = calcular_fibonacci(high_max, low_min)
    golden_pocket_low = fib['0.618']
    golden_pocket_high = fib['0.786']
    
    # 2. Soportes/Resistencias
    soportes, resistencias = detectar_soportes_resistencias(velas)
    soporte_cerca = any(abs(precio_actual - s) / precio_actual < UMBRAL_SOPORTE for s in soportes)
    resistencia_cerca = any(abs(precio_actual - r) / precio_actual < UMBRAL_SOPORTE for r in resistencias)
    
    # 3. FVG
    fvgs = detectar_fvg(velas)
    fvg_activo = any(not f['mitigado'] for f in fvgs)
    
    # 4. Order Blocks
    blocks = detectar_order_blocks(velas)
    block_cerca = any(abs(precio_actual - b['precio']) / precio_actual < UMBRAL_SOPORTE for b in blocks)
    
    # 5. Confluencia
    en_golden_pocket = golden_pocket_low <= precio_actual <= golden_pocket_high

    # 6. Media móvil (tendencia) y RSI (sobrecompra/sobreventa)
    ema = calcular_ema(velas, periodo=PERIODO_EMA)
    rsi = calcular_rsi(velas, periodo=PERIODO_RSI)
    tendencia_alcista = ema > 0 and precio_actual > ema
    tendencia_bajista = ema > 0 and precio_actual < ema
    rsi_sobrevendido = rsi < 30
    rsi_sobrecomprado = rsi > 70

    # Señal de compra (alcista)
    compra_score = 0
    if soporte_cerca:
        compra_score += 1
    if en_golden_pocket:
        compra_score += 1
    if fvg_activo and any(f['tipo'] == 'alcista' for f in fvgs):
        compra_score += 1
    if block_cerca and any(b['tipo'] == 'soporte' for b in blocks):
        compra_score += 1
    if tendencia_alcista:
        compra_score += 1
    if rsi_sobrevendido:
        compra_score += 1

    # Señal de venta (bajista)
    venta_score = 0
    if resistencia_cerca:
        venta_score += 1
    if en_golden_pocket:
        venta_score += 1  # también puede ser zona de reversión
    if fvg_activo and any(f['tipo'] == 'bajista' for f in fvgs):
        venta_score += 1
    if block_cerca and any(b['tipo'] == 'resistencia' for b in blocks):
        venta_score += 1
    if tendencia_bajista:
        venta_score += 1
    if rsi_sobrecomprado:
        venta_score += 1

    indicadores = {'ema_50': ema, 'rsi_14': rsi}

    # Decisión final (umbral de confluencia sobre 6 factores posibles)
    if compra_score >= UMBRAL_CONFLUENCIA:
        return {'senal': 'COMPRA', 'motivo': f'Confluencia alcista ({compra_score}/6)', 'score': compra_score, **indicadores}
    elif venta_score >= UMBRAL_CONFLUENCIA:
        return {'senal': 'VENTA', 'motivo': f'Confluencia bajista ({venta_score}/6)', 'score': venta_score, **indicadores}
    else:
        return {'senal': 'ESPERA', 'motivo': f'No hay confluencia suficiente (C:{compra_score}/V:{venta_score})', 'score': max(compra_score, venta_score), **indicadores}

# ========== CLASE PRINCIPAL ==========

class TradingLogic:
    """Motor de análisis profesional para criptomonedas."""
    
    def __init__(self):
        self.nombre = "Trader Profesional"
    
    def analizar(self, velas: List[Dict]) -> Dict[str, Any]:
        """
        Analiza velas y genera señal de trading con información detallada.
        """
        if not velas or len(velas) < 50:
            return {'senal': 'ESPERA', 'motivo': 'Datos insuficientes'}
        
        resultado = generar_senal(velas)
        
        # Agregar datos técnicos para depuración
        high_max = max(v['high'] for v in velas[-50:])
        low_min = min(v['low'] for v in velas[-50:])
        fib = calcular_fibonacci(high_max, low_min)
        resultado['fibonacci'] = {
            '0.618': fib['0.618'],
            '0.786': fib['0.786']
        }
        resultado['precio_actual'] = velas[-1]['close']
        resultado['timestamp'] = velas[-1]['tiempo']
        
        return resultado

# ========== EJECUCIÓN DIRECTA ==========
if __name__ == "__main__":
    import sys
    sys.path.append('.')
    from data_pipeline import PipelineVelas
    
    logging.basicConfig(level=logging.INFO)
    logger.info("🧪 Probando TradingLogic con datos reales...")
    
    pipeline = PipelineVelas()
    velas = pipeline.obtener_velas_para_analisis('BTC/USDT', '1H', 100)
    if velas:
        agente = TradingLogic()
        resultado = agente.analizar(velas)
        logger.info(f"Resultado: {resultado}")
    else:
        logger.error("No se pudieron obtener velas.")

def obtener_tendencias(activo):
    """Obtiene la última tendencia observada desde Supabase."""
    from core.db_manager import db
    try:
        result = db.table('tendencias_observadas').select('*').eq('activo', activo).order('created_at', desc=True).limit(1).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        print(f"⚠️ Error obteniendo tendencias: {e}")
        return None
