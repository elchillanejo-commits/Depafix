"""
Integración con la API de Mercado Público de Chile
(https://api.mercadopublico.cl/sitio_web/).

Estructura base: no se llama a la API real hasta contar con una
MERCADO_PUBLICO_API_KEY válida en el .env.
"""

import os
import logging

import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

BASE_URL = "https://api.mercadopublico.cl/servicios/v1/publico"
API_KEY = os.getenv("MERCADO_PUBLICO_API_KEY")
TIMEOUT_SEGUNDOS = 10


class MercadoPublicoError(Exception):
    pass


def buscar_contratos(proveedor_rut):
    """Consulta los contratos/órdenes de compra asociados a un proveedor por su RUT."""
    if not API_KEY:
        raise MercadoPublicoError("MERCADO_PUBLICO_API_KEY no está configurada")

    url = f"{BASE_URL}/ordenesdecompra.json"
    params = {"ticket": API_KEY, "rutProveedor": proveedor_rut}

    try:
        respuesta = requests.get(url, params=params, timeout=TIMEOUT_SEGUNDOS)
        respuesta.raise_for_status()
    except requests.Timeout as exc:
        logger.exception("Timeout al consultar contratos para %s", proveedor_rut)
        raise MercadoPublicoError("Timeout al consultar la API de Mercado Público") from exc
    except requests.RequestException as exc:
        logger.exception("Error al consultar contratos para %s", proveedor_rut)
        raise MercadoPublicoError(f"Error al consultar la API de Mercado Público: {exc}") from exc

    try:
        datos = respuesta.json()
    except ValueError as exc:
        raise MercadoPublicoError("Respuesta no es JSON válido") from exc

    contratos = datos.get("Listado") or []
    if not contratos:
        logger.warning("Sin contratos encontrados para el proveedor %s", proveedor_rut)
        return []

    return contratos


def obtener_precios_referencia(material):
    """Busca precios de referencia de un material dentro de los contratos disponibles."""
    if not API_KEY:
        raise MercadoPublicoError("MERCADO_PUBLICO_API_KEY no está configurada")

    url = f"{BASE_URL}/ordenesdecompra.json"
    params = {"ticket": API_KEY, "nombreProducto": material}

    try:
        respuesta = requests.get(url, params=params, timeout=TIMEOUT_SEGUNDOS)
        respuesta.raise_for_status()
    except requests.Timeout as exc:
        logger.exception("Timeout al buscar precios de %s", material)
        raise MercadoPublicoError("Timeout al consultar la API de Mercado Público") from exc
    except requests.RequestException as exc:
        logger.exception("Error al buscar precios de %s", material)
        raise MercadoPublicoError(f"Error al consultar la API de Mercado Público: {exc}") from exc

    try:
        datos = respuesta.json()
    except ValueError as exc:
        raise MercadoPublicoError("Respuesta no es JSON válido") from exc

    contratos = datos.get("Listado") or []
    if not contratos:
        logger.warning("Sin precios de referencia encontrados para %s", material)
        return []

    precios = []
    for contrato in contratos:
        items = contrato.get("Items", {}).get("Listado", [])
        for item in items:
            nombre = item.get("NombreProducto", "")
            if material.lower() in nombre.lower():
                precios.append({
                    "producto": nombre,
                    "precio_unitario": item.get("MontoUnitario"),
                    "cantidad": item.get("Cantidad"),
                    "codigo_orden": contrato.get("Codigo"),
                })

    return precios
