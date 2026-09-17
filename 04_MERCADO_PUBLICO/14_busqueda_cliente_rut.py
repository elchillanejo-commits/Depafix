#!/usr/bin/env python3
"""
Búsqueda personalizada de licitaciones para un cliente por RUT.
Filtros por defecto (Archiconstructor Limitada, RUT 76.296.338-8):
monto 10-50M, mejoramientos/remodelaciones, prioriza municipalidades
con historial de pago entre 30 y 45 días.
"""

import argparse
import importlib.util
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, '/home/ibar/Proyectos/DepaFix')
from core.db_manager import DatabaseManager

BASE_DIR = Path(__file__).resolve().parent

_spec = importlib.util.spec_from_file_location(
    "configuracion_oficios", BASE_DIR / "15_configuracion_oficios.py"
)
configuracion_oficios = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(configuracion_oficios)

RUT_CLIENTE_DEFAULT = "76.296.338-8"
NOMBRE_CLIENTE_DEFAULT = "Archiconstructor Limitada"
OFICIO_DEFAULT = "remodelacion"
MONTO_MIN_DEFAULT = 10_000_000
MONTO_MAX_DEFAULT = 50_000_000
DIAS_PAGO_MIN_DEFAULT = 30
DIAS_PAGO_MAX_DEFAULT = 45


def construir_filtro_texto(palabras_clave):
    """Arma el filtro or_ de PostgREST (debe ir separado por comas, sin espacios)."""
    condiciones = []
    for palabra in palabras_clave:
        condiciones.append(f"titulo.ilike.%{palabra}%")
        condiciones.append(f"descripcion.ilike.%{palabra}%")
    return ",".join(condiciones)


def buscar_licitaciones(db, monto_min, monto_max, palabras_clave, solo_vigentes=True):
    """Busca licitaciones dentro del rango de monto y con alguna palabra clave."""
    query = db.table("licitaciones") \
        .select("*") \
        .gte("monto_estimado", monto_min) \
        .lte("monto_estimado", monto_max) \
        .or_(construir_filtro_texto(palabras_clave))

    if solo_vigentes:
        query = query.gte("fecha_cierre", date.today().isoformat())

    try:
        result = query.execute()
        return result.data
    except Exception as e:
        print(f"❌ Error en búsqueda: {e}")
        return []


def contar_sin_monto(db, palabras_clave):
    """Cuenta licitaciones que calzan por palabra clave pero no tienen monto_estimado cargado."""
    try:
        result = db.table("licitaciones") \
            .select("id", count="exact") \
            .is_("monto_estimado", "null") \
            .or_(construir_filtro_texto(palabras_clave)) \
            .execute()
        return result.count or 0
    except Exception:
        return 0


def es_municipalidad(organismo: str) -> bool:
    if not organismo:
        return False
    organismo = organismo.lower()
    return "municipal" in organismo


def evaluar_pago(db, organismo, dias_min, dias_max):
    """Evalúa el historial real de pagos del organismo (tabla historial_pagos)."""
    result = db.table("historial_pagos").select("*").ilike("organismo", f"%{organismo}%").execute()
    registros = result.data

    if not registros:
        return {"cumple": None, "promedio_mora": None, "total_registros": 0}

    moras = [r["dias_mora"] for r in registros if r.get("dias_mora") is not None]
    if not moras:
        return {"cumple": None, "promedio_mora": None, "total_registros": len(registros)}

    promedio = sum(moras) / len(moras)
    return {
        "cumple": dias_min <= promedio <= dias_max,
        "promedio_mora": promedio,
        "total_registros": len(registros),
    }


def clasificar_prioridad(municipalidad: bool, pago: dict) -> str:
    if municipalidad and pago["cumple"] is True:
        return "🟢 PRIORITARIA"
    if municipalidad and pago["cumple"] is False:
        return "🟡 REVISAR (pago fuera de rango)"
    if municipalidad and pago["cumple"] is None:
        return "🟡 REVISAR (sin historial de pago)"
    return "⚪ EVALUAR (no es municipalidad)"


def enriquecer_licitacion(db, lic, dias_min, dias_max):
    municipalidad = es_municipalidad(lic.get("organismo"))
    pago = evaluar_pago(db, lic.get("organismo", ""), dias_min, dias_max)
    prioridad = clasificar_prioridad(municipalidad, pago)
    return {**lic, "es_municipalidad": municipalidad, "pago": pago, "prioridad": prioridad}


def generar_reporte(db, rut, nombre_cliente, oficio_clave, monto_min, monto_max,
                     dias_pago_min, dias_pago_max, solo_vigentes=True):
    oficio = configuracion_oficios.obtener_oficio(oficio_clave)
    palabras_clave = oficio["palabras_clave"]

    licitaciones = buscar_licitaciones(db, monto_min, monto_max, palabras_clave, solo_vigentes)
    enriquecidas = [enriquecer_licitacion(db, lic, dias_pago_min, dias_pago_max) for lic in licitaciones]
    enriquecidas.sort(key=lambda l: l["prioridad"])
    excluidas_sin_monto = contar_sin_monto(db, palabras_clave)

    return {
        "rut": rut,
        "cliente": nombre_cliente,
        "oficio": oficio["nombre"],
        "filtros": {
            "monto_min": monto_min,
            "monto_max": monto_max,
            "palabras_clave": palabras_clave,
            "dias_pago_min": dias_pago_min,
            "dias_pago_max": dias_pago_max,
            "solo_vigentes": solo_vigentes,
        },
        "resultados": enriquecidas,
        "excluidas_sin_monto_publicado": excluidas_sin_monto,
        "fecha_reporte": datetime.now().isoformat(),
    }


def imprimir_reporte(reporte: dict):
    print("\n" + "=" * 80)
    print(f"📋 REPORTE PARA {reporte['cliente']} (RUT {reporte['rut']})")
    print(f"🛠️  Oficio: {reporte['oficio']}")
    print("=" * 80)
    f = reporte["filtros"]
    print(f"📊 Filtros: ${f['monto_min']:,.0f} - ${f['monto_max']:,.0f} | "
          f"Pago objetivo: {f['dias_pago_min']}-{f['dias_pago_max']} días")
    print(f"🔍 Palabras clave: {', '.join(f['palabras_clave'])}")
    print("=" * 80)

    resultados = reporte["resultados"]
    if not resultados:
        print("\n⚠️ No se encontraron licitaciones que cumplan los filtros")
    else:
        print(f"\n📊 {len(resultados)} licitaciones encontradas")
        for i, lic in enumerate(resultados, 1):
            print(f"\n{i}. 🏷️  {lic.get('codigo_licitacion', 'N/A')} — {lic['prioridad']}")
            print(f"   📌 {lic.get('titulo', 'Sin título')[:80]}")
            print(f"   🏛️  Organismo: {lic.get('organismo', 'No especificado')}")
            print(f"   💰 Monto: ${lic.get('monto_estimado', 0):,.0f}")
            print(f"   📅 Publicación: {lic.get('fecha_publicacion', 'N/A')} | "
                  f"Cierre: {lic.get('fecha_cierre', 'N/A')}")
            print(f"   📍 Región/Comuna: {lic.get('region', 'N/A')} / {lic.get('comuna', 'N/A')}")

            pago = lic["pago"]
            if pago["cumple"] is True:
                print(f"   ✅ Historial de pago: {pago['promedio_mora']:.0f} días promedio "
                      f"({pago['total_registros']} registros) — dentro del rango")
            elif pago["cumple"] is False:
                print(f"   ⚠️ Historial de pago: {pago['promedio_mora']:.0f} días promedio "
                      f"({pago['total_registros']} registros) — fuera del rango")
            else:
                print("   ❓ Historial de pago: sin registros en historial_pagos")

    if reporte["excluidas_sin_monto_publicado"]:
        print(f"\nℹ️  {reporte['excluidas_sin_monto_publicado']} licitaciones adicionales calzan por "
              f"palabra clave pero no tienen monto_estimado publicado (no se pueden evaluar).")

    print("\n" + "=" * 80)
    print(f"📅 Reporte generado: {reporte['fecha_reporte']}")
    print("=" * 80)


def obtener_o_crear_contratista(db, rut: str, nombre_cliente: str, palabras_clave) -> int:
    """suscripciones no tiene columna RUT: se busca por nombre y, si no existe, se crea."""
    result = db.table("suscripciones").select("id").eq("cliente_nombre", nombre_cliente).execute()
    if result.data:
        return result.data[0]["id"]

    nuevo = db.table("suscripciones").insert({
        "cliente_nombre": nombre_cliente,
        "cliente_email": f"{rut.replace('.', '').replace('-', '')}@sin-email.cl",
        "palabras_clave": palabras_clave,
        "activo": True,
    }).execute()
    return nuevo.data[0]["id"]


def guardar_reporte(db, reporte: dict):
    contratista_id = obtener_o_crear_contratista(
        db, reporte["rut"], reporte["cliente"], reporte["filtros"]["palabras_clave"]
    )
    db.table("reportes_contratista").insert({
        "contratista_id": contratista_id,
        "licitacion_id": None,
        "contenido": reporte,
        "formato": "JSON",
        "creado_por": "14_busqueda_cliente_rut.py",
    }).execute()
    print(f"\n✅ Reporte guardado en Supabase (contratista_id={contratista_id})")


def main():
    parser = argparse.ArgumentParser(description="Búsqueda personalizada de licitaciones por RUT")
    parser.add_argument("--rut", default=RUT_CLIENTE_DEFAULT, help="RUT del cliente")
    parser.add_argument("--cliente", default=NOMBRE_CLIENTE_DEFAULT, help="Nombre del cliente")
    parser.add_argument("--oficio", default=OFICIO_DEFAULT,
                         help=f"Clave de oficio (ver 15_configuracion_oficios.py). Default: {OFICIO_DEFAULT}")
    parser.add_argument("--monto-min", type=float, default=MONTO_MIN_DEFAULT)
    parser.add_argument("--monto-max", type=float, default=MONTO_MAX_DEFAULT)
    parser.add_argument("--dias-pago-min", type=int, default=DIAS_PAGO_MIN_DEFAULT)
    parser.add_argument("--dias-pago-max", type=int, default=DIAS_PAGO_MAX_DEFAULT)
    parser.add_argument("--todas-fechas", action="store_true",
                         help="Incluir licitaciones ya cerradas (por defecto solo vigentes)")
    parser.add_argument("--guardar", action="store_true", help="Guardar reporte en Supabase")
    args = parser.parse_args()

    print(f"🔍 Buscando licitaciones para {args.cliente} (RUT {args.rut}), oficio '{args.oficio}'...")
    db = DatabaseManager().get_service_client()

    reporte = generar_reporte(
        db, args.rut, args.cliente, args.oficio,
        args.monto_min, args.monto_max,
        args.dias_pago_min, args.dias_pago_max,
        solo_vigentes=not args.todas_fechas,
    )
    imprimir_reporte(reporte)

    if args.guardar:
        guardar_reporte(db, reporte)


if __name__ == "__main__":
    main()
