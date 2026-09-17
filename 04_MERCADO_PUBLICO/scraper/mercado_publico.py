"""
Scraper para la API pública de Mercado Público de Chile
(https://api.mercadopublico.cl/servicios/v1/publico/licitaciones.json).

Consulta licitaciones filtradas por rubro y estado, extrae los precios
unitarios de los materiales/ítems adjudicados y guarda el resultado en CSV
o JSON.

Requiere una MERCADO_PUBLICO_API_KEY válida en el .env.

Uso:
    python scrapers/mercado_publico.py --rubro "Construcción" --estado adjudicada --limite 20 --salida data/precios_construccion.json
"""

import argparse
import csv
import json
import logging
import os
import time

import psycopg2
import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Único endpoint real: no existe una variante "licitacion.json" (singular) para
# el detalle por código -- devuelve 404. Tanto el listado como el detalle por
# `codigo` se consultan contra esta misma URL (verificado contra la API real).
BASE_URL = "https://api.mercadopublico.cl/servicios/v1/publico/licitaciones.json"
API_KEY = os.getenv("MERCADO_PUBLICO_API_KEY")
# Misma conexión que usa api.py para /api/rubros (línea que alimenta la Pirámide
# de Costos del dashboard): psycopg2 directo contra Supabase vía SUPABASE_DB_URL.
SUPABASE_DB_URL = os.getenv("SUPABASE_DB_URL")
TIMEOUT_SEGUNDOS = 10
PAUSA_ENTRE_LLAMADAS_SEGUNDOS = 1.5
REINTENTOS_429 = 4

ESTADOS_VALIDOS = ["activas", "publicada", "cerrada", "desierta", "adjudicada", "revocada", "suspendida", "todos"]


class MercadoPublicoError(Exception):
    pass


def _get(params):
    espera = 2
    for intento in range(1, REINTENTOS_429 + 1):
        try:
            respuesta = requests.get(BASE_URL, params=params, timeout=TIMEOUT_SEGUNDOS)
            if respuesta.status_code == 429 and intento < REINTENTOS_429:
                logger.warning("429 recibido, reintentando en %ss (intento %s)", espera, intento)
                time.sleep(espera)
                espera *= 2
                continue
            respuesta.raise_for_status()
        except requests.Timeout as exc:
            logger.exception("Timeout al consultar Mercado Público (params=%s)", params)
            raise MercadoPublicoError("Timeout al consultar la API de Mercado Público") from exc
        except requests.RequestException as exc:
            logger.exception("Error al consultar Mercado Público (params=%s)", params)
            raise MercadoPublicoError(f"Error al consultar la API de Mercado Público: {exc}") from exc

        try:
            return respuesta.json()
        except ValueError as exc:
            raise MercadoPublicoError("Respuesta no es JSON válido") from exc


def buscar_licitaciones_por_rubro(rubro, estado="activas", limite=10, fecha=None):
    """Busca licitaciones cuyo nombre/descripción coincidan con `rubro`.

    La API de Mercado Público no tiene un parámetro de búsqueda por rubro, y
    el listado masivo (por `estado`) siempre devuelve `Items: null` (sin
    detalle de ítems/precios, verificado contra la API real). Por eso primero
    se pide el listado por `estado` (liviano) y se filtra localmente por
    `rubro` contra el nombre/descripción; luego se consulta el detalle de
    cada candidata por `codigo` (única forma de obtener `Items` con precios
    unitarios) hasta reunir `limite` coincidencias.

    `fecha` (formato ddmmaaaa) permite acotar el listado masivo a un día
    específico en vez del comportamiento por defecto de `estado` solo, que
    únicamente devuelve licitaciones con cambio de estado el día de hoy
    (confirmado contra la API real: `estado=adjudicada` sin fecha == mismo día).
    """
    if not API_KEY:
        raise MercadoPublicoError("MERCADO_PUBLICO_API_KEY no está configurada")

    params = {"ticket": API_KEY, "estado": estado}
    if fecha:
        params["fecha"] = fecha
    datos = _get(params)
    listado = datos.get("Listado") or []
    if not listado:
        logger.warning("Sin licitaciones para el estado %s (fecha=%s)", estado, fecha)
        return []

    rubro_lower = rubro.lower()
    candidatas = [
        lic for lic in listado
        if rubro_lower in (lic.get("Nombre") or "").lower()
        or rubro_lower in (lic.get("Descripcion") or "").lower()
    ]
    logger.info("Candidatas por nombre/descripción: %d de %d", len(candidatas), len(listado))

    licitaciones_filtradas = []
    for resumen in candidatas:
        codigo = resumen.get("CodigoExterno")
        if not codigo:
            continue
        time.sleep(PAUSA_ENTRE_LLAMADAS_SEGUNDOS)
        detalle = _get({"ticket": API_KEY, "codigo": codigo})
        listado_detalle = detalle.get("Listado") or []
        if not listado_detalle:
            continue
        licitaciones_filtradas.append(listado_detalle[0])
        if len(licitaciones_filtradas) >= limite:
            break

    if not licitaciones_filtradas:
        logger.warning("Sin licitaciones encontradas para el rubro %s en estado %s", rubro, estado)

    return licitaciones_filtradas


def extraer_precios_unitarios(licitaciones):
    """Recorre las licitaciones y extrae cada ítem con su precio unitario adjudicado."""
    precios = []
    for licitacion in licitaciones:
        items = (licitacion.get("Items") or {}).get("Listado") or []
        fecha_adjudicacion = (licitacion.get("Fechas") or {}).get("FechaAdjudicacion")
        for item in items:
            adjudicacion = item.get("Adjudicacion") or {}
            monto_unitario = adjudicacion.get("MontoUnitario")
            if monto_unitario is None:
                continue
            precios.append({
                "codigo_licitacion": licitacion.get("CodigoExterno"),
                "nombre_licitacion": licitacion.get("Nombre"),
                "proveedor": adjudicacion.get("NombreProveedor"),
                "producto": item.get("NombreProducto"),
                "categoria": item.get("Categoria"),
                "codigo_producto": item.get("CodigoProducto"),
                "cantidad": item.get("Cantidad"),
                "unidad_medida": item.get("UnidadMedida"),
                "precio_unitario": monto_unitario,
                "fecha_adjudicacion": fecha_adjudicacion,
            })

    if not precios:
        logger.warning("No se encontraron precios unitarios en las licitaciones entregadas")

    return precios


def guardar_en_line_items(precios, rubro):
    """Guarda/actualiza los precios extraídos en la tabla line_items de Supabase.

    Si ya existe una fila con el mismo (material, rubro) se actualiza
    precio_unitario con el valor más reciente (no se promedia); si no existe,
    se inserta una fila nueva con record_id NULL (no vinculada a ningún
    presupuesto/record). No hay constraint UNIQUE sobre (material, rubro) en
    la tabla, por lo que la deduplicación se hace a mano vía SELECT+UPDATE.
    """
    if not SUPABASE_DB_URL:
        raise MercadoPublicoError("SUPABASE_DB_URL no está configurada")

    insertados = 0
    actualizados = 0
    conn = psycopg2.connect(SUPABASE_DB_URL)
    try:
        with conn:
            with conn.cursor() as cur:
                for p in precios:
                    material = p.get("producto")
                    if not material:
                        continue
                    cantidad = p.get("cantidad") or 1
                    precio_unitario = p.get("precio_unitario")
                    if precio_unitario is None:
                        continue

                    cur.execute(
                        "SELECT line_item_id FROM line_items WHERE material = %s AND rubro = %s",
                        (material, rubro),
                    )
                    existente = cur.fetchone()
                    if existente:
                        cur.execute(
                            "UPDATE line_items SET precio_unitario = %s, cantidad = %s WHERE line_item_id = %s",
                            (precio_unitario, cantidad, existente[0]),
                        )
                        actualizados += 1
                    else:
                        cur.execute(
                            "INSERT INTO line_items (record_id, material, cantidad, precio_unitario, rubro) "
                            "VALUES (NULL, %s, %s, %s, %s)",
                            (material, cantidad, precio_unitario, rubro),
                        )
                        insertados += 1
    finally:
        conn.close()

    return insertados, actualizados


def guardar_en_precios_serviu(precios, rubro):
    """Inserta los precios extraídos en la tabla precios_serviu de DepaFix
    (fuente='MERCADO_PUBLICO'), usada por /predict. Es la misma tabla donde ya
    viven los registros de SERVIU (fuente='SERVIU'). idempotency_key es
    UNIQUE en la tabla, así que el insert usa ON CONFLICT DO NOTHING -- no
    duplica si ya se cargó antes.

    La tabla real (confirmado via information_schema.columns, no vía el .sql
    del repo) es id/item/unidad/valor_unitario/fuente/idempotency_key/
    created_at -- NO tiene columnas `moneda` ni `rubro` pese a lo que decía
    este docstring antes (la migración que las agregaría nunca se aplicó en
    vivo). `rubro` se sigue recibiendo como parámetro para el hash de
    idempotencia y el log, pero no se persiste -- no hay dónde.

    Cada fila se inserta en su propio commit: si una fila falla (dato corrupto,
    constraint, etc.) se loguea y se sigue con las demás en vez de perder todo
    el lote por un solo error (ver auditor_precios_ia.py para el saneamiento
    posterior de filas con estado_dato='ERROR_DATOS').
    """
    import hashlib
    from datetime import datetime, timezone

    if not SUPABASE_DB_URL:
        raise MercadoPublicoError("SUPABASE_DB_URL no está configurada")

    nuevos = 0
    conn = psycopg2.connect(SUPABASE_DB_URL)
    try:
        for p in precios:
            item = p.get("producto")
            precio_unitario = p.get("precio_unitario")
            if not item or precio_unitario is None:
                continue
            unidad = p.get("unidad_medida")
            idem = hashlib.sha256(
                f"mp_{item}_{unidad}_{p.get('codigo_licitacion')}".encode()
            ).hexdigest()
            try:
                with conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            """
                            INSERT INTO precios_serviu
                                (item, unidad, valor_unitario, fuente, idempotency_key, created_at)
                            VALUES (%s, %s, %s, 'MERCADO_PUBLICO', %s, %s)
                            ON CONFLICT (idempotency_key) DO NOTHING
                            """,
                            (item, unidad, precio_unitario, idem, datetime.now(timezone.utc)),
                        )
                        if cur.rowcount:
                            nuevos += 1
            except psycopg2.Error as exc:
                logger.error("No se pudo insertar '%s' (rubro=%s) en precios_serviu: %s", item, rubro, exc)
    finally:
        conn.close()

    return nuevos


def guardar_resultados(datos, formato, path):
    """Guarda los resultados en CSV o JSON en la ruta indicada."""
    formato = formato.lower()
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)

    if formato == "json":
        with open(path, "w", encoding="utf-8") as f:
            json.dump(datos, f, ensure_ascii=False, indent=2)
    elif formato == "csv":
        if not datos:
            with open(path, "w", encoding="utf-8") as f:
                f.write("")
            return
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(datos[0].keys()))
            writer.writeheader()
            writer.writerows(datos)
    else:
        raise ValueError(f"Formato no soportado: {formato}")


def main():
    parser = argparse.ArgumentParser(description="Scraper de precios de Mercado Público por rubro")
    parser.add_argument("--rubro", required=True, help="Texto a buscar en nombre/descripción de la licitación (ej. 'Construcción')")
    parser.add_argument("--estado", choices=ESTADOS_VALIDOS, default="activas", help="Estado de licitación a consultar")
    parser.add_argument("--formato", choices=["csv", "json"], default="json")
    parser.add_argument("--salida", default="resultados.json", help="Ruta del archivo de salida (por defecto resultados.json)")
    parser.add_argument("--limite", type=int, default=10, help="Número máximo de licitaciones a consultar (por defecto 10)")
    parser.add_argument("--fecha", default=None, help="Fecha ddmmaaaa para acotar el listado masivo a ese día (por defecto: solo el día de hoy)")
    args = parser.parse_args()

    licitaciones = buscar_licitaciones_por_rubro(args.rubro, args.estado, args.limite, fecha=args.fecha)
    precios = extraer_precios_unitarios(licitaciones)
    guardar_resultados(precios, args.formato, args.salida)
    print(f"Licitaciones consultadas: {len(licitaciones)}")
    print(f"Guardados {len(precios)} precios unitarios en {args.salida}")

    insertados, actualizados = guardar_en_line_items(precios, args.rubro)
    print(f"Supabase (line_items): {insertados} insertados, {actualizados} actualizados (rubro='{args.rubro}')")

    nuevos_precios_serviu = guardar_en_precios_serviu(precios, args.rubro)
    print(f"Supabase (precios_serviu): {nuevos_precios_serviu} nuevos (fuente=MERCADO_PUBLICO)")


if __name__ == "__main__":
    main()
