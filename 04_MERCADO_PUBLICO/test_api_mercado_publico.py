#!/usr/bin/env python3
"""
Prueba de conexión a la API pública de Mercado Público (ChileCompra).

Los endpoints con base `apis.mercadopublico.cl` (RSS y v1) devuelven 404 --
no son el dominio correcto. El servicio real es:

    https://api.mercadopublico.cl/servicios/v1/publico/licitaciones.json

Autenticación vía query param `ticket` (la API Key), no headers especiales.
Params soportados: codigo, fecha (ddmmaaaa), estado (publicada/activas/...),
CodigoProveedor, CodigoOrganismo -- no hay filtro de texto libre ni rubro.

Dos pasos para datos completos:
  1. Listado por fecha+estado -> solo trae CodigoExterno/Nombre/CodigoEstado/FechaCierre.
  2. Detalle por codigo -> trae Comprador, Fechas, MontoEstimado, Descripcion, Items, etc.

`fecha` es un día puntual, no un rango -- una consulta a una fecha muy temprano
en el día (poco después de medianoche en Chile) puede devolver 0 resultados
simplemente porque aún no se ha publicado nada ese día.
"""
import json
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

API_BASE = "https://api.mercadopublico.cl/servicios/v1/publico/licitaciones.json"
TICKET = os.getenv("MERCADO_PUBLICO_API_KEY")


def listar_por_fecha(fecha_ddmmaaaa: str, estado: str = "publicada") -> dict:
    resp = requests.get(API_BASE, params={"ticket": TICKET, "fecha": fecha_ddmmaaaa, "estado": estado}, timeout=30)
    resp.raise_for_status()
    return resp.json()


def detalle_licitacion(codigo: str) -> dict:
    resp = requests.get(API_BASE, params={"ticket": TICKET, "codigo": codigo}, timeout=30)
    resp.raise_for_status()
    return resp.json()


def main():
    if not TICKET:
        print("❌ Falta MERCADO_PUBLICO_API_KEY en .env", file=sys.stderr)
        sys.exit(1)

    print(f"🔑 Ticket configurado: {TICKET[:8]}...")
    print(f"🌐 Endpoint: {API_BASE}\n")

    # `fecha` es un día puntual: si hoy aún no tiene publicaciones, cae a ayer.
    for dias_atras in (0, 1, 2):
        fecha = (datetime.now() - timedelta(days=dias_atras)).strftime("%d%m%Y")
        print(f"📅 Probando fecha={fecha} estado=publicada ...")
        data = listar_por_fecha(fecha, estado="publicada")
        cantidad = data.get("Cantidad", 0)
        print(f"   Cantidad: {cantidad}")
        if cantidad:
            break
        time.sleep(1)
    else:
        print("❌ No se encontraron licitaciones en los últimos 3 días.", file=sys.stderr)
        sys.exit(1)

    listado = data["Listado"]
    print(f"\n✅ Listado obtenido ({len(listado)} licitaciones). Estructura de un item del listado:")
    print(json.dumps(listado[0], indent=2, ensure_ascii=False))

    print("\n🔎 Consultando detalle completo de las primeras 5 (para Comprador/Fechas/Monto)...\n")
    ejemplos = []
    for item in listado[:5]:
        codigo = item["CodigoExterno"]
        time.sleep(0.5)  # evitar "peticiones simultáneas" (Codigo 10500)
        detalle = detalle_licitacion(codigo)
        if not detalle.get("Listado"):
            continue
        d = detalle["Listado"][0]
        ejemplos.append(d)
        comprador = d.get("Comprador", {}) or {}
        fechas = d.get("Fechas", {}) or {}
        print(f"  • {d['CodigoExterno']} | {d['Nombre'][:60]}")
        print(f"    Organismo: {comprador.get('NombreOrganismo')}")
        print(f"    Región/Comuna: {comprador.get('RegionUnidad')} / {comprador.get('ComunaUnidad')}")
        print(f"    Monto estimado: {d.get('MontoEstimado')} {d.get('Moneda')}")
        print(f"    Publicación: {fechas.get('FechaPublicacion')} | Cierre: {fechas.get('FechaCierre')}")
        print()

    if not ejemplos:
        print("❌ No se pudo obtener detalle de ninguna licitación.", file=sys.stderr)
        sys.exit(1)

    print(f"✅ Prueba exitosa: {len(ejemplos)}/5 licitaciones reales obtenidas con detalle completo.")


if __name__ == "__main__":
    main()
