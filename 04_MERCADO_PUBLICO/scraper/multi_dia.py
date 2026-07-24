#!/usr/bin/env python3
"""
Recorre los últimos N días llamando a buscar_licitaciones_por_rubro() para
varios rubros, con estado=adjudicada y fecha=ddmmaaaa, y acumula los precios
en precios_serviu (fuente=MERCADO_PUBLICO) y line_items.

Batch -- un solo ciclo por ejecución, sin loop interno (ver REGLAS DE ORO en
06_AGENTES/GEMINI_OUTPUT/SYSTEM_PROMPT_CLAUDE.md: la cadencia la maneja cron/
Railway Schedules, no un while True acá). Reporta a salud_agentes al
terminar, igual que trading_orchestrator.py.

Uso:
    python3 scrapers/multi_dia.py --dias 7 --limite 15
"""
import argparse
import json
import sys
import time
import traceback
from datetime import datetime, timedelta
from pathlib import Path

from mercado_publico import (
    buscar_licitaciones_por_rubro,
    extraer_precios_unitarios,
    guardar_en_precios_serviu,
    guardar_en_line_items,
    MercadoPublicoError,
)

# Ruta relativa a este archivo (repo_root/04_MERCADO_PUBLICO/scraper/multi_dia.py
# -> repo_root/procurador), en vez de la absoluta hardcodeada original -- esa
# solo funcionaba en esta máquina; acá tiene que funcionar también dentro del
# contenedor Docker (repo copiado a /app).
CORE_PATH = Path(__file__).resolve().parents[2] / "procurador"
if str(CORE_PATH) not in sys.path:
    sys.path.insert(0, str(CORE_PATH))

NOMBRE_PROCESO = "mercado_publico_multi_dia"

RUBROS = {
    "Construcción": ["Construcción"],
    "Electricidad": ["Electricidad"],
    "Fontanería": ["Fontanería"],
    "Gráfica": ["Gráfica", "Publicidad", "Impresión"],
    "Capacitación": ["Capacitación"],
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dias", type=int, default=7)
    parser.add_argument("--limite", type=int, default=15)
    args = parser.parse_args()

    resumen = {rubro: {"licitaciones": 0, "precios_extraidos": 0, "precios_nuevos_serviu": 0, "ejemplos": []} for rubro in RUBROS}
    total_licitaciones = 0
    total_precios = 0

    for offset in range(args.dias):
        fecha_dt = datetime.now() - timedelta(days=offset)
        fecha_str = fecha_dt.strftime("%d%m%Y")
        print(f"\n=== Día {fecha_str} ===")

        for rubro, sinonimos in RUBROS.items():
            precios_dia = []
            licitaciones_dia = 0
            for sinonimo in sinonimos:
                try:
                    licitaciones = buscar_licitaciones_por_rubro(
                        sinonimo, estado="adjudicada", limite=args.limite, fecha=fecha_str
                    )
                except MercadoPublicoError as exc:
                    print(f"  ERROR {rubro} ({sinonimo}) {fecha_str}: {exc}")
                    continue

                if licitaciones:
                    licitaciones_dia += len(licitaciones)
                    precios_dia.extend(extraer_precios_unitarios(licitaciones))
                    break  # ya encontramos algo con este sinónimo, no seguir probando otros

            if precios_dia:
                nuevos = guardar_en_precios_serviu(precios_dia, rubro)
                guardar_en_line_items(precios_dia, rubro)
                resumen[rubro]["licitaciones"] += licitaciones_dia
                resumen[rubro]["precios_extraidos"] += len(precios_dia)
                resumen[rubro]["precios_nuevos_serviu"] += nuevos
                for p in precios_dia[:5]:
                    if len(resumen[rubro]["ejemplos"]) < 5:
                        resumen[rubro]["ejemplos"].append(p)
                total_licitaciones += licitaciones_dia
                total_precios += len(precios_dia)
                print(f"  {rubro}: {licitaciones_dia} licitaciones, {len(precios_dia)} precios, {nuevos} nuevos en precios_serviu")
            else:
                print(f"  {rubro}: sin resultados")

            time.sleep(1)

    print("\n\n===== RESUMEN FINAL =====")
    print(json.dumps(resumen, ensure_ascii=False, indent=2, default=str))
    print(f"\nTotal licitaciones procesadas: {total_licitaciones}")
    print(f"Total precios unitarios extraídos: {total_precios}")

    Path("datos").mkdir(exist_ok=True)
    with open("datos/resumen_multidia.json", "w", encoding="utf-8") as f:
        json.dump(resumen, f, ensure_ascii=False, indent=2, default=str)

    return total_licitaciones, total_precios


def main_con_salud():
    from core.db_manager import DatabaseManager
    from core.salud_agentes import reportar_salud

    db = None
    try:
        db = DatabaseManager().get_service_client()
    except Exception as e:
        print(f"No se pudo inicializar Supabase (service_role) para telemetria: {e}")

    try:
        total_licitaciones, total_precios = main()
    except Exception:
        detalle = traceback.format_exc()
        reportar_salud(db, NOMBRE_PROCESO, "CRITICAL", detalle[-500:])
        raise

    reportar_salud(
        db, NOMBRE_PROCESO, "HEALTHY",
        f"{total_licitaciones} licitacion(es), {total_precios} precio(s) extraido(s).",
        metricas={"total_licitaciones": total_licitaciones, "total_precios": total_precios},
    )


if __name__ == "__main__":
    main_con_salud()
