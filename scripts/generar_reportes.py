#!/usr/bin/env python3
"""
Generador de reportes quincenales y mensuales desde datos reales de Supabase.
Uso: python scripts/generar_reportes.py --auto  (ejecuta quincenal y mensual)
"""
import sys
import os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.trading.analisis_periodico import generar_reporte_quincenal, generar_reporte_mensual, mostrar_resumen

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--auto', action='store_true', help='Ejecuta quincenal y mensual')
    parser.add_argument('--quincenal', action='store_true')
    parser.add_argument('--mensual', action='store_true')
    parser.add_argument('--resumen', action='store_true')
    args = parser.parse_args()

    if args.auto:
        print("📊 Generando reporte quincenal...")
        generar_reporte_quincenal()
        print("📊 Generando reporte mensual...")
        generar_reporte_mensual()
    elif args.quincenal:
        generar_reporte_quincenal()
    elif args.mensual:
        generar_reporte_mensual()
    elif args.resumen:
        mostrar_resumen()
    else:
        print("⚠️ Usa --auto, --quincenal, --mensual o --resumen")
