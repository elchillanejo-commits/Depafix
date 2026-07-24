#!/usr/bin/env python3
"""
Entrypoint único para cron/Railway Cron Schedule. Llama a
multi_dia.main_con_salud() con los mismos parámetros que ya usa el cron
local instalado (--dias 1 --limite 15): un ciclo por ejecución, la cadencia
la maneja el scheduler externo, no un loop interno acá.

No reimplementa nada de mercado_publico.py/multi_dia.py -- ambos ya son
idempotentes (line_items vía SELECT+INSERT/UPDATE por material+rubro,
precios_serviu vía ON CONFLICT DO NOTHING sobre idempotency_key) y ya
reportan a salud_agentes. Este script solo fija los defaults de producción
y sirve de comando estable para invocar desde afuera (cron local o Railway).

Uso:
    python3 run_scraper.py
    python3 run_scraper.py --dias 2 --limite 20
"""
import argparse
import sys

import multi_dia


def main():
    parser = argparse.ArgumentParser(description="Ejecuta el ciclo diario del scraper de Mercado Público")
    parser.add_argument("--dias", type=int, default=1, help="Días hacia atrás a recorrer (default: 1, uso diario)")
    parser.add_argument("--limite", type=int, default=15, help="Licitaciones máximas por rubro/día (default: 15)")
    args = parser.parse_args()

    sys.argv = ["multi_dia.py", "--dias", str(args.dias), "--limite", str(args.limite)]
    multi_dia.main_con_salud()


if __name__ == "__main__":
    main()
