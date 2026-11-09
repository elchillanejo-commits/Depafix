#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DepaFix Ingeniero de Datos — scraper_sodimac.py
================================================
Scraper para Sodimac.cl (React SPA) que guarda en Supabase:
    retailers, productos, precios_historial

Estrategia de extracción (orden de prioridad):
  A) Interceptar respuestas de red (page.on('response')) para capturar los JSON
     de las APIs internas. No se parsea el HTML para obtener nombre/SKU/precio.
  B) Fallback: leer JSON-LD (<script type="application/ld+json">, Schema.org).

Como Sodimac renderiza el listado de categoría en HTML (SSR) y no expone un JSON
de producto independiente en la red, el flujo es:
  1. Navegar a la categoría (ej. Pinturas).
  2. Descubrir las URLs de detalle de producto en el listado (solo URL, no dato).
  3. Visitar cada detalle y extraer nombre/SKU/precio exclusivamente con A + B.
  4. Guardar en Supabase (retailers -> productos -> precios_historial).

Variables de entorno (en .env):
    SUPABASE_URL
    SUPABASE_SERVICE_ROLE_KEY  (o SUPABASE_KEY / SUPABASE_ANON_KEY)
"""

import argparse
import asyncio
import json
import logging
import os
import random
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse, urljoin

from dotenv import load_dotenv
from playwright.async_api import async_playwright
from supabase import create_client

# --------------------------------------------------------------------------- #
# Configuración general
# --------------------------------------------------------------------------- #
LOG = logging.getLogger("scraper_sodimac")

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)
URL_BASE_SODIMAC = "https://www.sodimac.cl/"
URL_CATEGORIA_PINTURAS = (
    "https://www.sodimac.cl/sodimac-cl/lista/CATG36265/Pinturas"
)
URL_MOCK = "https://www.sodimac.cl/sodimac-cl/articulo/123456/pintura-latex-blanco-1-galon/123456789"

# Archivo por defecto con una URL de categoría por línea (admite comentarios #).
URLS_CATEGORIAS_DEFAULT = (
    Path(__file__).resolve().parents[2] / "urls_categorias.txt"
)

# Secciones base del catálogo de construcción. Se usan si no existe el archivo,
# o como complemento para garantizar variedad de materiales.
URLS_CATEGORIAS_FALLBACK = [
    "https://www.sodimac.cl/sodimac-cl/lista/CATG10753/Materiales-de-Obra-Gruesa",
    "https://www.sodimac.cl/sodimac-cl/lista/CATG10731/Materiales-de-Construccion",
    "https://www.sodimac.cl/sodimac-cl/lista/CATG10741/Pisos-y-revestimientos",
    "https://www.sodimac.cl/sodimac-cl/lista/CATG10923/Cemento",
    "https://www.sodimac.cl/sodimac-cl/lista/CATG10925/Yeso",
    "https://www.sodimac.cl/sodimac-cl/lista/CATG10754/Fierro",
    "https://www.sodimac.cl/sodimac-cl/lista/CATG10732/maderas-y-tableros",
]

# Claves que indican precio / nombre / sku dentro de los JSON interceptados.
CLAVES_PRECIO = (
    "price", "precio", "saleprice", "listprice", "preciooferta",
    "preciolista", "bestprice", "amount", "unitprice", "offerprice",
)
CLAVES_NOMBRE = (
    "name", "nombre", "title", "descripcion", "description",
    "displayname", "originalproductname", "productname",
)
CLAVES_SKU = ("sku", "id", "productid", "codigoproducto", "itemid", "partnumber", "mpn")

# Umbral para considerar que un precio es real (CLP). Sodimac publica precios
# de miles de pesos; valores como $5 son falsos positivos de la red.
PRECIO_MINIMO_REAL = 1000.0

# Filtro de descubierta de URLs: catálogo completo, excluyendo servicios.
TERMINOS_SERVICIO = (
    "instalacion", "instalación", "visita", "presupuesto", "seguro",
    "contratar", "montaje", "fumigacion", "servicio", "proyecto",
    "despacho", "armado", "anclaje",
)

# Categorías válidas (solo construcción). Evita colados no relacionados
# (electrodomésticos, tecnología, etc., ej. "plancha de vapor Xiaomi").
# Se valida por keywords en categoría/nombre/URL (normalizado a minúsculas).
CATEGORIAS_CONSTRUCCION_VALIDAS = (
    # obra gruesa / estructurales
    "cemento", "hormigon", "hormigón", "mortero", "concreto", "ladrillo",
    "bloque", "arena", "ripio", "gravilla", "arido", "árido",
    "fierro", "acero", "malla acma", "alambre", "perfil", "metalcon",
    "yeso", "estuco", "pastina", "frague", "fragüe",
    # madera / tableros
    "madera", "tablero", "terciado", "osb", "mdf", "melamina", "pino",
    "viga", "pilar", "moldura",
    # terminaciones / revestimientos
    "pintura", "esmalte", "latex", "látex", "barniz", "sellante",
    "ceramica", "cerámica", "porcelanato", "piso", "revestimiento",
    "adhesivo", "pegamento", "silicona",
    # techumbre / aislación / tabiquería
    "techo", "techumbre", "zinc", "aislacion", "aislación", "lana",
    "volcanita", "yeso carton", "yeso cartón", "tabique",
    # ferretería / fijaciones de obra
    "tornillo", "clavo", "perno", "anclaje", "fijacion", "fijación",
    # gasfitería / electricidad de obra básica (materiales)
    "tuberia", "tubería", "codo", "llave paso", "cable", "canalizacion",
    # generales de construcción
    "construccion", "construcción", "obra", "materiales",
)

CATEGORIAS_CONSTRUCCION_EXCLUIDAS = (
    "electrodomest", "linea blanca", "línea blanca", "tecnolog", "comput",
    "notebook", "celular", "telefono", "teléfono", "audio", "televisor",
    "tv", "smartwatch", "reloj", "consola", "videojuego",
    "plancha de vapor", "plancha vapor", "vaporizador", "xiaomi",
    "aspiradora", "freidora", "licuadora", "cafetera", "microondas",
    "refrigerador", "lavadora", "secadora", "belleza", "cuidado personal",
    "juguete", "deporte", "mascota", "moda", "ropa", "calzado",
)


def _normalizar_texto_categoria(texto: str) -> str:
    return (texto or "").lower().strip()


def es_categoria_construccion_valida(
    categoria: Optional[str] = None,
    nombre: Optional[str] = None,
    url: Optional[str] = None,
) -> bool:
    """True si el producto parece material de construcción y no un excluido.

    Política: si hay señal de exclusión explícita -> False. Si hay señal de
    construcción válida -> True. Si no hay señales (categoría vacía/ambigua),
    se permite (fail-open) para no descartar productos de obra sin metadata.
    """
    texto = " ".join([
        _normalizar_texto_categoria(categoria),
        _normalizar_texto_categoria(nombre),
        _normalizar_texto_categoria(url),
    ])
    if any(term in texto for term in CATEGORIAS_CONSTRUCCION_EXCLUIDAS):
        return False
    if not categoria and not nombre:
        return True
    if any(term in texto for term in CATEGORIAS_CONSTRUCCION_VALIDAS):
        return True
    # Sin match explícito: permitir solo si venimos de contexto de categoría
    # conocido (categoría provista) o si no hay categoría para juzgar.
    return bool(categoria) or not bool(nombre)


def es_url_de_producto(url: str) -> bool:
    """True si la URL es un detalle de producto y no un servicio."""
    slug = urlparse(url).path.lower()
    if any(t in slug for t in TERMINOS_SERVICIO):
        return False
    return bool(re.search(r"/articulo/\d+/", slug))


def es_url_de_pintura(url: str) -> bool:
    """Compatibilidad con versiones anteriores."""
    return es_url_de_producto(url)


# --------------------------------------------------------------------------- #
# Entorno y Supabase
# --------------------------------------------------------------------------- #
def cargar_env() -> Optional[Path]:
    """Busca y carga el .env en varias ubicaciones candidatas."""
    candidatos = [
        Path(__file__).resolve().parents[2] / ".env",          # repo/.env
        Path.home() / "DepaFix_Maestro" / ".env",
        Path.cwd() / ".env",
    ]
    for ruta in candidatos:
        if ruta.exists():
            load_dotenv(ruta)
            LOG.info("Variables de entorno cargadas desde %s", ruta)
            return ruta
    load_dotenv()
    LOG.warning("No se encontró .env explícito; se usa load_dotenv() por defecto")
    return None


def get_supabase():
    cargar_env()
    url = os.getenv("SUPABASE_URL")
    key = (
        os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        or os.getenv("SUPABASE_KEY")
        or os.getenv("SUPABASE_ANON_KEY")
    )
    if not url or not key:
        raise RuntimeError(
            "Faltan credenciales de Supabase en .env: SUPABASE_URL y "
            "SUPABASE_SERVICE_ROLE_KEY/SUPABASE_KEY/SUPABASE_ANON_KEY"
        )
    return create_client(url, key)


def asegurar_retailer(sb, nombre="Sodimac", url_base=URL_BASE_SODIMAC) -> dict:
    existente = (
        sb.table("retailers").select("*").eq("nombre", nombre).limit(1).execute()
    )
    if existente.data:
        return existente.data[0]
    insertado = sb.table("retailers").insert(
        {"nombre": nombre, "url_base": url_base}
    ).execute()
    return insertado.data[0]


def asegurar_producto(
    sb, retailer_id: str, sku: str, descripcion: str,
    unidad: Optional[str] = None, categoria: Optional[str] = None,
) -> dict:
    existente = (
        sb.table("productos")
        .select("*")
        .eq("sku", sku)
        .eq("retailer_id", retailer_id)
        .limit(1)
        .execute()
    )
    if existente.data:
        actual = existente.data[0]
        cambios: Dict[str, Any] = {}
        if (
            descripcion
            and descripcion != "Producto Sodimac"
            and descripcion != actual.get("descripcion")
        ):
            cambios["descripcion"] = descripcion
        if unidad and unidad != actual.get("unidad"):
            cambios["unidad"] = unidad
        if categoria and categoria != actual.get("categoria"):
            cambios["categoria"] = categoria
        if cambios:
            try:
                actualizado = (
                    sb.table("productos")
                    .update(cambios)
                    .eq("id", actual["id"])
                    .execute()
                )
                if actualizado.data:
                    return actualizado.data[0]
            except Exception as exc:
                LOG.warning(
                    "No se pudo actualizar metadata de %s: %s", sku, exc
                )
        return actual
    payload: Dict[str, Any] = {
        "retailer_id": retailer_id,
        "sku": sku,
        "descripcion": descripcion,
    }
    if unidad:
        payload["unidad"] = unidad
    if categoria:
        payload["categoria"] = categoria
    insertado = sb.table("productos").insert(payload).execute()
    return insertado.data[0]


def guardar_precio(
    sb, producto_id: str, precio_neto: float,
    precio_lista: Optional[float], url_producto: str,
) -> dict:
    lista = float(precio_lista if precio_lista is not None else precio_neto)
    payload = {
        "producto_id": producto_id,
        "precio_neto": round(lista / 1.19),
        "precio_lista": lista,
        "url_producto": url_producto,
    }
    insertado = sb.table("precios_historial").insert(payload).execute()
    return insertado.data[0] if insertado.data else payload


# --------------------------------------------------------------------------- #
# Utilidades de normalización
# --------------------------------------------------------------------------- #
def normalizar_clave(clave: str) -> str:
    return re.sub(r"[^a-z]", "", str(clave).lower())


def a_numero(valor: Any) -> Optional[float]:
    """Convierte '$ 79.762,00' / '79762' / 79762 en float, o None."""
    if isinstance(valor, bool):
        return None
    if isinstance(valor, (int, float)):
        return float(valor)
    if isinstance(valor, str):
        limpio = re.sub(r"[^0-9,.\-]", "", valor.replace("$", "").strip())
        if not limpio:
            return None
        try:
            # Formato CLP: separador miles '.', decimales ',' -> normalizar a punto
            if "," in limpio and "." in limpio:
                limpio = limpio.replace(".", "").replace(",", ".")
            else:
                limpio = limpio.replace(",", ".")
            return float(limpio)
        except ValueError:
            return None
    return None


def es_diccionario_producto(nodo: Dict[str, Any]) -> bool:
    """Heurística: un dict parece producto si tiene nombre-like y precio-like."""
    claves = {normalizar_clave(k) for k in nodo.keys()}
    tiene_nombre = any(
        normalizar_clave(c) in claves or any(
            normalizar_clave(c) in nk for nk in claves
        ) for c in CLAVES_NOMBRE
    )
    tiene_precio = any(
        normalizar_clave(c) in claves or any(
            normalizar_clave(c) in nk for nk in claves
        ) for c in CLAVES_PRECIO
    )
    return bool(tiene_nombre and tiene_precio)


def extraer_de_dict(nodo: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Intenta extraer {nombre, sku, precio_neto, precio_lista} de un dict."""
    nombre = None
    sku = None
    precios: List[float] = []
    for clave, valor in nodo.items():
        nc = normalizar_clave(clave)
        if nc in CLAVES_SKU or nc.endswith(tuple(CLAVES_SKU)):
            if isinstance(valor, (str, int)) and not sku:
                sku = str(valor)
        if nc in CLAVES_NOMBRE or nc.endswith(tuple(CLAVES_NOMBRE)):
            if isinstance(valor, str) and len(valor) > 3 and not nombre:
                nombre = valor
        if nc in CLAVES_PRECIO or nc.endswith(tuple(CLAVES_PRECIO)):
            num = a_numero(valor)
            if num is not None and num > 0:
                precios.append(num)
    if not precios:
        return None
    precios_ord = sorted(precios)
    return {
        "nombre": nombre or "Producto Sodimac",
        "sku": sku or "SODIMAC-SIN-SKU",
        "precio_neto": precios_ord[0],
        "precio_lista": precios_ord[-1],
    }


def recorrer_json(node: Any, resultados: List[Dict[str, Any]]) -> None:
    """Recorre recursivamente un JSON buscando diccionarios con producto+precio."""
    if isinstance(node, dict):
        if es_diccionario_producto(node):
            res = extraer_de_dict(node)
            if res:
                resultados.append(res)
        for valor in node.values():
            recorrer_json(valor, resultados)
    elif isinstance(node, list):
        for item in node:
            recorrer_json(item, resultados)


# --------------------------------------------------------------------------- #
# Estrategia A: interceptar respuestas de red
# --------------------------------------------------------------------------- #
class RedJsonCaptor:
    """Captura respuestas JSON de la red mientras navega."""

    def __init__(self) -> None:
        self.payloads: List[Any] = []

    async def handler(self, response) -> None:
        try:
            content_type = response.headers.get("content-type", "") or ""
            if "application/json" not in content_type:
                return
            datos = await response.json()
            self.payloads.append(datos)
        except Exception:
            # Respuestas JSON no parseables o sin cuerpo: se ignoran.
            pass


def candidato_valido(c: Dict[str, Any]) -> bool:
    """Descarta falsos positivos (seguros, servicios, precios simbólicos) y no-construcción."""
    sku = str(c.get("sku") or "").strip()
    precio = c.get("precio_neto") or 0
    nombre = str(c.get("nombre") or "").lower()
    categoria = c.get("categoria")
    url = c.get("url")
    if not sku or sku == "SODIMAC-SIN-SKU":
        return False
    if precio < PRECIO_MINIMO_REAL:
        return False
    if any(x in nombre for x in (
        "seguro", "contratar", "despacho", "servicio", "instalación",
        "instalacion", "proyecto", "mano de obra", "armado", "anclaje",
    )):
        return False
    if not es_categoria_construccion_valida(categoria, nombre, url):
        return False
    return True


def parsear_json_red(payloads: List[Any]) -> Optional[Dict[str, Any]]:
    """Busca el mejor candidato de producto entre todos los JSON interceptados."""
    candidatos: List[Dict[str, Any]] = []
    for payload in payloads:
        try:
            recorrer_json(payload, candidatos)
        except Exception:
            continue
    candidatos = [c for c in candidatos if candidato_valido(c)]
    if not candidatos:
        return None
    # Elegir el candidato con más información (nombre + sku + precio).
    def puntaje(c: Dict[str, Any]) -> int:
        return sum(
            1 for k in ("nombre", "sku", "precio_neto")
            if c.get(k) not in (None, "", "SODIMAC-SIN-SKU")
        )
    candidatos.sort(key=puntaje, reverse=True)
    return candidatos[0]


# --------------------------------------------------------------------------- #
# Estrategia B: JSON-LD (Schema.org)
# --------------------------------------------------------------------------- #
UNIDADES_EXPLICITAS = (
    ("saco", "saco"), ("bolsa", "saco"), ("galón", "galón"),
    ("galon", "galón"), ("tineta", "tineta"), ("balde", "balde"),
    ("plancha", "plancha"), ("tablero", "tablero"), ("tabla", "tabla"),
    ("barra", "barra"), ("perfil", "barra"), ("tubo", "tubo"),
    ("rollo", "rollo"), ("caja", "caja"), ("pack", "pack"),
    ("m2", "m2"), ("m3", "m3"),
)


def unidad_desde_nombre(nombre: str, categoria: Optional[str] = None) -> str:
    """Normaliza la unidad comercial: saco, barra, plancha, m2, unidad, etc."""
    texto = f"{nombre or ''} {categoria or ''}".lower()

    # 1) Unidad explícita en el nombre o categoría (ej. "25 kg Saco").
    for palabra, unidad in UNIDADES_EXPLICITAS:
        if re.search(rf"\b{re.escape(palabra)}\b", texto):
            return unidad

    # 2) Reglas por familia de material.
    if any(k in texto for k in ("yeso cartón", "yeso carton", "volcanita")):
        return "plancha"
    if any(k in texto for k in ("fierro", "acero", "malla acma", "perfil metalcon")):
        return "barra"
    if any(k in texto for k in (
        "cemento", "yeso", "mortero", "estuco", "hormigón", "hormigon",
        "árido", "arido", "arena", "adhesivo", "fragüe", "frague",
    )):
        return "saco"
    if any(k in texto for k in (
        "madera", "pino", "terciado", "osb", "mdf", "melamina",
        "vigas", "pilar", "tablero",
    )):
        return "unidad"
    if any(k in texto for k in (
        "cerámica", "ceramica", "porcelanato", "piso", "revestimiento",
    )):
        return "m2"
    if any(k in texto for k in ("pintura", "esmalte", "látex", "latex")):
        return "galón"
    return "unidad"


def parsear_ld_json(
    html: str, categoria_hint: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Busca un objeto Product en los bloques <script type='application/ld+json'>."""
    bloques = re.findall(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html, re.S | re.I,
    )
    mejores: List[Dict[str, Any]] = []
    categoria: Optional[str] = None
    for bloque in bloques:
        try:
            datos = json.loads(bloque.strip())
        except Exception:
            continue
        items = datos if isinstance(datos, list) else [datos]
        for item in items:
            if not isinstance(item, dict):
                continue
            tipo = str(item.get("@type", "")).lower()
            if "breadcrumblist" in tipo:
                elementos = item.get("itemListElement") or []
                if elementos and isinstance(elementos[-1], dict):
                    categoria = categoria or elementos[-1].get("name")
                continue
            if "product" not in tipo:
                continue
            nombre = item.get("name") or item.get("description") or "Producto Sodimac"
            sku = str(
                item.get("sku")
                or item.get("mpn")
                or item.get("productID")
                or "SODIMAC-SIN-SKU"
            )
            ofertas = item.get("offers") or {}
            if isinstance(ofertas, list):
                ofertas = ofertas[0] if ofertas else {}
            precio = a_numero(
                ofertas.get("price")
                or ofertas.get("lowPrice")
                or item.get("price")
            )
            precio_lista = a_numero(
                ofertas.get("highPrice") or ofertas.get("price")
            )
            if precio is not None and precio > 0:
                categoria_producto = (
                    str(item.get("category") or "").strip()
                    or categoria
                    or categoria_hint
                )
                mejores.append({
                    "nombre": str(nombre),
                    "sku": sku,
                    "precio_neto": float(precio),
                    "precio_lista": float(precio_lista if precio_lista else precio),
                    "categoria": categoria_producto,
                    "unidad": unidad_desde_nombre(
                        str(nombre), categoria_producto
                    ),
                })
    if not mejores:
        return None
    # Devolver el primero válido (JSON-LD suele traer el producto principal).
    for mejor in mejores:
        if not mejor.get("categoria"):
            mejor["categoria"] = categoria or categoria_hint
    return mejores[0]


# --------------------------------------------------------------------------- #
# Extracción por página (Estrategia A + B)
# --------------------------------------------------------------------------- #
def resultado_es_valido(r: Optional[Dict[str, Any]]) -> bool:
    """True si el resultado tiene SKU, precio real, es construcción y no servicio."""
    if not r:
        return False
    if r.get("sku") in (None, "", "SODIMAC-SIN-SKU"):
        return False
    if (r.get("precio_neto") or 0) < PRECIO_MINIMO_REAL:
        return False
    nombre = str(r.get("nombre") or "")
    if any(x in nombre.lower() for x in (
        "seguro", "contratar", "servicio", "instalación", "instalacion",
        "proyecto", "despacho", "mano de obra", "armado", "anclaje",
    )):
        return False
    if not es_categoria_construccion_valida(
        r.get("categoria"), nombre, r.get("url")
    ):
        LOG.info("Producto excluido por categoría no-construcción: %s", nombre[:80])
        return False
    return True


def seleccionar_resultado(
    resultado_a: Optional[Dict[str, Any]],
    resultado_b: Optional[Dict[str, Any]],
    url: str,
    categoria_hint: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Normaliza y elige el mejor resultado: JSON-LD tiene prioridad."""
    for resultado in (resultado_a, resultado_b):
        if not resultado:
            continue
        resultado["url"] = url
        if not resultado.get("categoria"):
            resultado["categoria"] = categoria_hint or "Construcción"
        if not resultado.get("unidad"):
            resultado["unidad"] = unidad_desde_nombre(
                str(resultado.get("nombre") or ""),
                resultado.get("categoria"),
            )
    if resultado_a:
        resultado_a["estrategia"] = "A_page.on_response_JSON"
    if resultado_b:
        resultado_b["estrategia"] = "B_ld+json_Schema.org"

    if resultado_es_valido(resultado_b):
        return resultado_b
    if resultado_es_valido(resultado_a):
        return resultado_a
    return None


async def extraer_producto(
    url: str, headless: bool = True, timeout_ms: int = 60000,
    categoria_hint: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Extrae nombre/SKU/precio de una página de producto Sodimac.

    Estrategia A: intercepta respuestas JSON de la red.
    Estrategia B: lee JSON-LD (Schema.org).
    Nunca se extrae nombre/SKU/precio parseando el HTML.

    Se ejecutan A y B y se queda con el mejor resultado: prefiere el que tenga
    precio real (>= PRECIO_MINIMO_REAL) y, entre válidos, prioriza JSON-LD
    porque es el más estructurado y confiable en Sodimac.
    """
    captor = RedJsonCaptor()
    html: str = ""
    titulo = ""

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=headless,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        contexto = await browser.new_context(
            user_agent=USER_AGENT,
            locale="es-CL",
            timezone_id="America/Santiago",
            viewport={"width": 1366, "height": 768},
            extra_http_headers={
                "Accept-Language": "es-CL,es;q=0.9,en;q=0.8",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
        )
        page = await contexto.new_page()
        page.on("response", captor.handler)

        try:
            LOG.info("[A] Navegando a producto: %s", url)
            await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            await page.wait_for_timeout(random.randint(2000, 4000))
            try:
                await page.wait_for_load_state("networkidle", timeout=5000)
            except Exception:
                pass
            await page.wait_for_timeout(random.randint(1200, 2200))
            html = await page.content()
            titulo = await page.title()
        except Exception as exc:
            LOG.error("[A] Falló navegación a %s: %s", url, exc)
            await browser.close()
            return None
        finally:
            await browser.close()

    LOG.info("[A] JSONs interceptados: %d | Título: %s", len(captor.payloads), titulo)

    # Estrategia A: red
    resultado_a = parsear_json_red(captor.payloads)

    # Estrategia B: JSON-LD
    LOG.info("[B] Probando JSON-LD (Schema.org)")
    resultado_b = parsear_ld_json(html, categoria_hint=categoria_hint)

    elegido = seleccionar_resultado(
        resultado_a, resultado_b, url, categoria_hint
    )
    if elegido is None:
        LOG.warning("[A+B] No se pudo extraer un producto válido de %s", url)
    return elegido


async def extraer_real(url: str, headless: bool = True, timeout_ms: int = 60000) -> Optional[Dict[str, Any]]:
    return await extraer_producto(url, headless=headless, timeout_ms=timeout_ms)


def extraer_mock(url: str = URL_MOCK) -> Dict[str, Any]:
    return {
        "nombre": "Pintura Látex Blanco 1 Galón (mock)",
        "sku": "PINT-LAT-01",
        "precio_neto": 12500.0,
        "precio_lista": 15800.0,
        "url": url,
        "estrategia": "mock_sin_red",
    }


async def descubrir_urls_producto(
    url_categoria: str, headless: bool = True, timeout_ms: int = 60000,
    max_productos: int = 20,
) -> List[str]:
    """Descubre URLs de detalle de producto en una página de listado/categoría.

    Solo se obtienen URLs (descubrimiento). El dato (nombre/SKU/precio) se extrae
    después en cada detalle con la Estrategia A + B.
    """
    urls: List[str] = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=headless,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        contexto = await browser.new_context(
            user_agent=USER_AGENT,
            locale="es-CL",
            timezone_id="America/Santiago",
            viewport={"width": 1366, "height": 768},
        )
        page = await contexto.new_page()
        try:
            LOG.info("[Listado] Navegando categoría: %s", url_categoria)
            ultimo_error: Optional[Exception] = None
            for intento in range(1, 3):
                try:
                    await page.goto(
                        url_categoria, wait_until="domcontentloaded",
                        timeout=timeout_ms,
                    )
                    ultimo_error = None
                    break
                except Exception as exc:
                    ultimo_error = exc
                    LOG.warning(
                        "[Listado] Reintento %d/2 en %s: %s",
                        intento, url_categoria, exc,
                    )
                    await page.wait_for_timeout(2000)
            if ultimo_error is not None:
                raise ultimo_error
            await page.wait_for_timeout(random.randint(2500, 4000))

            # Scroll para disparar el lazy-load de la grilla de productos.
            for _ in range(6):
                await page.mouse.wheel(0, 3000)
                await page.wait_for_timeout(random.randint(600, 1000))

            # Enlaces de producto Sodimac: .../articulo/<id>/<slug>/<id>
            enlaces = await page.evaluate(
                """() => {
                    const anchors = Array.from(document.querySelectorAll('a[href]'));
                    return anchors.map(a => a.href).filter(h =>
                        /sodimac-cl\\/articulo\\/\\d+/.test(h)
                    );
                }"""
            )
            visto = set()
            for u in enlaces:
                u = u.split("?")[0].split("#")[0]
                if u in visto:
                    continue
                visto.add(u)
                if not es_url_de_producto(u):
                    continue
                urls.append(u)
                if len(urls) >= max_productos:
                    break
            LOG.info("[Listado] URLs de producto válidas: %d", len(urls))
        except Exception as exc:
            LOG.error("[Listado] Falló descubrimiento en %s: %s", url_categoria, exc)
        finally:
            await browser.close()
    return urls


def etiqueta_desde_url(url: str) -> str:
    """Deriva una etiqueta legible desde el slug final de la URL."""
    slug = urlparse(url).path.rstrip("/").split("/")[-1]
    etiqueta = re.sub(r"[-_]+", " ", slug).strip()
    return etiqueta.title() if etiqueta else "Construcción"


def leer_urls_categorias(ruta: Path) -> List[Dict[str, str]]:
    """Lee urls_categorias.txt.

    Formatos aceptados por línea:
        https://.../lista/CATG.../Categoria
        Etiqueta visible | https://.../lista/CATG.../Categoria

    Las líneas vacías y todo lo que sigue a '#' se ignoran.
    """
    if not ruta.exists():
        LOG.warning("No existe %s; usando categorías por defecto", ruta)
        return [
            {"url": u, "categoria": etiqueta_desde_url(u)}
            for u in URLS_CATEGORIAS_FALLBACK
        ]

    categorias: List[Dict[str, str]] = []
    vistos = set()
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        linea = linea.split("#", 1)[0].strip()
        if not linea:
            continue
        etiqueta = ""
        if "|" in linea:
            etiqueta, linea = [parte.strip() for parte in linea.split("|", 1)]
        if not urlparse(linea).scheme:
            linea = urljoin(URL_BASE_SODIMAC, linea)
        if linea in vistos:
            continue
        vistos.add(linea)
        categorias.append({
            "url": linea,
            "categoria": etiqueta or etiqueta_desde_url(linea),
        })

    if not categorias:
        LOG.warning("El archivo %s no contiene URLs; usando fallback", ruta)
        return [
            {"url": u, "categoria": etiqueta_desde_url(u)}
            for u in URLS_CATEGORIAS_FALLBACK
        ]
    return categorias


# --------------------------------------------------------------------------- #
# Flujo principal
# --------------------------------------------------------------------------- #
async def extraer_lote(
    items: List[Dict[str, str]], headless: bool = True, timeout_ms: int = 60000,
) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Extrae varios productos reutilizando un solo navegador.

    Cada URL se procesa de forma aislada: un timeout, bloqueo o página sin
    datos se registra en el log y se continúa con la siguiente URL.
    """
    resultados: List[Dict[str, Any]] = []
    errores: List[Dict[str, Any]] = []
    vistos_sku = set()

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=headless,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        contexto = await browser.new_context(
            user_agent=USER_AGENT,
            locale="es-CL",
            timezone_id="America/Santiago",
            viewport={"width": 1366, "height": 900},
            extra_http_headers={
                "Accept-Language": "es-CL,es;q=0.9,en;q=0.8",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
        )
        try:
            for i, item in enumerate(items, 1):
                url = item["url"]
                categoria_hint = item.get("categoria")
                LOG.info(
                    "=== Producto %d/%d [%s]: %s",
                    i, len(items), categoria_hint or "sin categoría", url,
                )
                captor = RedJsonCaptor()
                page = await contexto.new_page()
                page.on("response", captor.handler)
                try:
                    ultimo_error: Optional[Exception] = None
                    for intento in range(1, 3):
                        try:
                            await page.goto(
                                url, wait_until="domcontentloaded",
                                timeout=timeout_ms,
                            )
                            ultimo_error = None
                            break
                        except Exception as exc:
                            ultimo_error = exc
                            LOG.warning(
                                "Reintento %d/2 en %s: %s",
                                intento, url, exc,
                            )
                            await page.wait_for_timeout(1500)
                    if ultimo_error is not None:
                        raise ultimo_error
                    await page.wait_for_timeout(random.randint(1200, 2200))
                    try:
                        await page.wait_for_load_state("networkidle", timeout=3000)
                    except Exception:
                        pass
                    html = await page.content()
                except Exception as exc:
                    LOG.error(
                        "Error en %s (%s): %s",
                        url, type(exc).__name__, exc,
                    )
                    errores.append({
                        "url": url,
                        "categoria": categoria_hint,
                        "error": f"{type(exc).__name__}: {exc}",
                    })
                    await page.close()
                    continue
                await page.close()

                resultado_a = parsear_json_red(captor.payloads)
                resultado_b = parsear_ld_json(
                    html, categoria_hint=categoria_hint
                )
                dato = seleccionar_resultado(
                    resultado_a, resultado_b, url, categoria_hint
                )
                if not dato:
                    LOG.warning("Sin datos válidos en %s", url)
                    errores.append({
                        "url": url,
                        "categoria": categoria_hint,
                        "error": "sin datos de producto válidos",
                    })
                    continue

                sku = dato.get("sku")
                if sku in vistos_sku:
                    LOG.info("SKU duplicado omitido: %s", sku)
                    continue
                vistos_sku.add(sku)
                resultados.append(dato)
                LOG.info(
                    "OK %s | %s | lista=$%.0f | unidad=%s | categoria=%s",
                    sku, str(dato.get("nombre"))[:70],
                    dato.get("precio_lista") or 0,
                    dato.get("unidad"), dato.get("categoria"),
                )
                await asyncio.sleep(random.uniform(0.6, 1.4))
        finally:
            await browser.close()

    return resultados, errores


async def scrapear_categoria(
    url_categoria: str, max_productos: int, headless: bool, timeout_ms: int,
    categoria_hint: Optional[str] = None,
) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Descubre y extrae los productos de una categoría."""
    urls = await descubrir_urls_producto(
        url_categoria, headless=headless, timeout_ms=timeout_ms,
        max_productos=max_productos,
    )
    if not urls:
        LOG.warning("No se descubrieron URLs de producto en la categoría.")
        return [], []

    hint = categoria_hint or etiqueta_desde_url(url_categoria)
    items = [{"url": url, "categoria": hint} for url in urls]
    return await extraer_lote(
        items, headless=headless, timeout_ms=timeout_ms
    )


async def scrapear_categorias(
    categorias: List[Dict[str, str]], max_productos: int,
    headless: bool, timeout_ms: int,
) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Recorre todas las categorías sin detenerse ante errores puntuales."""
    resultados: List[Dict[str, Any]] = []
    errores: List[Dict[str, Any]] = []
    vistos_sku = set()

    for idx, categoria in enumerate(categorias, 1):
        url = categoria["url"]
        hint = categoria.get("categoria") or etiqueta_desde_url(url)
        LOG.info(
            "\n### Categoría %d/%d: %s (%s)",
            idx, len(categorias), hint, url,
        )
        try:
            datos, errs = await scrapear_categoria(
                url,
                max_productos=max_productos,
                headless=headless,
                timeout_ms=timeout_ms,
                categoria_hint=hint,
            )
        except Exception as exc:
            LOG.error(
                "Categoría omitida %s (%s): %s",
                url, type(exc).__name__, exc,
            )
            errores.append({
                "url": url,
                "categoria": hint,
                "error": f"{type(exc).__name__}: {exc}",
            })
            continue

        errores.extend(errs)
        for dato in datos:
            sku = dato.get("sku")
            if sku in vistos_sku:
                continue
            vistos_sku.add(sku)
            resultados.append(dato)
        LOG.info(
            "Categoría %s: +%d productos | acumulado=%d",
            hint, len(datos), len(resultados),
        )

    return resultados, errores


def guardar_en_supabase(resultados: List[Dict[str, Any]]) -> Dict[str, int]:
    """Inserta retailer, productos y precios_historial en Supabase."""
    resumen = {
        "retailer": 0,
        "productos": 0,
        "nuevos": 0,
        "actualizados": 0,
        "precios": 0,
        "errores": 0,
    }
    if not resultados:
        return resumen

    try:
        sb = get_supabase()
    except Exception as exc:
        LOG.error("No se pudo conectar a Supabase: %s", exc)
        resumen["errores"] = len(resultados)
        return resumen

    try:
        retailer = asegurar_retailer(sb)
        resumen["retailer"] = 1
        retailer_id = retailer["id"]
        LOG.info("[Supabase] retailer: %s %s", retailer_id, retailer.get("nombre"))
        existentes = (
            sb.table("productos")
            .select("sku")
            .eq("retailer_id", retailer_id)
            .execute()
        )
        skus_existentes = {fila.get("sku") for fila in existentes.data}
    except Exception as exc:
        LOG.error("Error asegurando retailer: %s", exc)
        resumen["errores"] = len(resultados)
        return resumen

    for dato in resultados:
        sku = str(dato.get("sku") or "").strip()
        if not sku:
            LOG.warning("Producto sin SKU omitido: %s", dato.get("nombre"))
            resumen["errores"] += 1
            continue
        try:
            producto = asegurar_producto(
                sb,
                retailer_id=retailer_id,
                sku=sku,
                descripcion=dato.get("nombre") or "Producto Sodimac",
                unidad=dato.get("unidad") or "unidad",
                categoria=dato.get("categoria") or "Construcción",
            )
            resumen["productos"] += 1
            if sku in skus_existentes:
                resumen["actualizados"] += 1
            else:
                resumen["nuevos"] += 1
                skus_existentes.add(sku)
            LOG.info(
                "[Supabase] producto: %s sku=%s unidad=%s categoria=%s",
                producto["id"], producto.get("sku"),
                producto.get("unidad"), producto.get("categoria"),
            )
        except Exception as exc:
            LOG.error("Error asegurando producto %s: %s", sku, exc)
            resumen["errores"] += 1
            continue

        try:
            precio = guardar_precio(
                sb,
                producto_id=producto["id"],
                precio_neto=dato.get("precio_neto") or 0,
                precio_lista=dato.get("precio_lista"),
                url_producto=dato.get("url") or "",
            )
            resumen["precios"] += 1
            LOG.info(
                "[Supabase] precios_historial insertado: precio_neto=$%.0f",
                precio.get("precio_neto", 0) if isinstance(precio, dict) else 0,
            )
        except Exception as exc:
            LOG.error("Error guardando precio para %s: %s", dato.get("sku"), exc)
            resumen["errores"] += 1

    return resumen


# --------------------------------------------------------------------------- #
# Punto de entrada
# --------------------------------------------------------------------------- #
def configurar_logging(log_file: Optional[Path]) -> None:
    handlers: List[logging.Handler] = [logging.StreamHandler(sys.stdout)]
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=handlers,
    )


def contar_productos() -> Dict[str, int]:
    """Cuenta filas y SKUs únicos en la tabla productos."""
    try:
        sb = get_supabase()
        filas = sb.table("productos").select("sku").execute().data
        unicos = {f.get("sku") for f in filas if f.get("sku")}
        return {"total": len(filas), "unicos": len(unicos)}
    except Exception as exc:
        LOG.error("No se pudo contar productos en Supabase: %s", exc)
        return {"total": -1, "unicos": -1}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Scraper Sodimac (async Playwright) -> Supabase "
                    "(retailers, productos, precios_historial)"
    )
    parser.add_argument(
        "--urls-categorias", default=str(URLS_CATEGORIAS_DEFAULT),
        help="Archivo TXT con una URL de categoría por línea",
    )
    parser.add_argument(
        "--categoria", default=None,
        help="URL de una única categoría (reemplaza al archivo)",
    )
    parser.add_argument(
        "--max-productos", type=int, default=8,
        help="Máximo de productos a extraer por categoría",
    )
    parser.add_argument(
        "--headed", action="store_true",
        help="Ejecutar Playwright con ventana visible",
    )
    parser.add_argument(
        "--timeout", type=int, default=45000,
        help="Timeout de navegación en ms",
    )
    parser.add_argument(
        "--solo-producto", default=None,
        help="Extraer una única URL de producto (evita recorrer categorías)",
    )
    parser.add_argument(
        "--sin-validacion", action="store_true",
        help="No ejecutar el validador de precios al finalizar",
    )
    parser.add_argument(
        "--log-file",
        default=str(
            Path(__file__).resolve().parents[2] / "logs" / "scraper_sodimac.log"
        ),
        help="Ruta del log de ejecución",
    )
    args = parser.parse_args()

    configurar_logging(Path(args.log_file) if args.log_file else None)

    print("=" * 70)
    print("DepaFix Ingeniero de Datos — scraper_sodimac.py (async Playwright)")
    print("=" * 70)

    cargar_env()
    errores: List[Dict[str, Any]] = []
    resultados: List[Dict[str, Any]] = []
    guardado_incremental = False
    resumen_total = {
        "retailer": 0,
        "productos": 0,
        "nuevos": 0,
        "actualizados": 0,
        "precios": 0,
        "errores": 0,
    }

    try:
        if args.solo_producto:
            url = args.solo_producto
            if not urlparse(url).scheme:
                url = urljoin(URL_BASE_SODIMAC, url)
            resultado_uno = asyncio.run(extraer_producto_directo(
                url, headless=not args.headed, timeout_ms=args.timeout
            ))
            resultados = [resultado_uno] if resultado_uno else []
        elif args.categoria:
            resultados, errores = asyncio.run(scrapear_categoria(
                args.categoria,
                max_productos=args.max_productos,
                headless=not args.headed,
                timeout_ms=args.timeout,
                categoria_hint=etiqueta_desde_url(args.categoria),
            ))
        else:
            categorias = leer_urls_categorias(Path(args.urls_categorias))
            LOG.info("Categorías a recorrer: %d", len(categorias))
            vistos = set()
            for idx, categoria in enumerate(categorias, 1):
                url_cat = categoria["url"]
                hint = categoria.get("categoria") or etiqueta_desde_url(url_cat)
                LOG.info(
                    "\n### Categoría %d/%d: %s (%s)",
                    idx, len(categorias), hint, url_cat,
                )
                try:
                    datos, errs = asyncio.run(scrapear_categoria(
                        url_cat,
                        max_productos=args.max_productos,
                        headless=not args.headed,
                        timeout_ms=args.timeout,
                        categoria_hint=hint,
                    ))
                except Exception as exc:
                    LOG.error(
                        "Categoría omitida %s (%s): %s",
                        url_cat, type(exc).__name__, exc,
                    )
                    errores.append({
                        "url": url_cat,
                        "categoria": hint,
                        "error": f"{type(exc).__name__}: {exc}",
                    })
                    continue

                errores.extend(errs)
                nuevos: List[Dict[str, Any]] = []
                for dato in datos:
                    sku = dato.get("sku")
                    if sku in vistos:
                        continue
                    vistos.add(sku)
                    resultados.append(dato)
                    nuevos.append(dato)
                LOG.info(
                    "Categoría %s: +%d nuevos | acumulado=%d",
                    hint, len(nuevos), len(resultados),
                )
                if nuevos:
                    parcial = guardar_en_supabase(nuevos)
                    for clave in resumen_total:
                        resumen_total[clave] += parcial.get(clave, 0)
                    print(f"Guardado parcial [{hint}]: {parcial}")
            guardado_incremental = True
            if resultados:
                resumen_total["retailer"] = 1
    except Exception as exc:
        print(
            f"Error: extracción real falló ({type(exc).__name__}: {exc})",
            file=sys.stderr,
        )
        sys.exit(1)

    print("-" * 70)
    print(f"Productos extraídos con éxito: {len(resultados)}")
    print(f"Errores/omitidos registrados: {len(errores)}")
    for r in resultados:
        print(
            f"  - {r.get('sku')} | {str(r.get('nombre'))[:55]} | "
            f"lista=${(r.get('precio_lista') or 0):,.0f} | "
            f"unidad={r.get('unidad')} | categoria={r.get('categoria')}"
        )

    print("-" * 70)
    print(json.dumps(resultados, ensure_ascii=False, indent=2, default=str))

    if not resultados:
        print(
            "Error: extracción sin resultados. No se insertará nada en Supabase.",
            file=sys.stderr,
        )
        sys.exit(1)

    if not guardado_incremental:
        resumen_total = guardar_en_supabase(resultados)
    print("-" * 70)
    print("Resumen Supabase:", resumen_total)

    if not args.sin_validacion:
        try:
            sys.path.insert(0, str(Path(__file__).resolve().parent))
            from run_validacion import ejecutar_validacion
            print("-" * 70)
            print("Ejecutando validador de precios automático...")
            validacion = ejecutar_validacion(30)
            print("Resumen validación:", validacion)
        except Exception as exc:
            LOG.error("Falló la validación automática: %s", exc)

    conteo = contar_productos()
    print("-" * 70)
    print(
        f"Productos en tabla productos: total={conteo['total']} | "
        f"únicos_sku={conteo['unicos']}"
    )
    print(f"Log de ejecución: {args.log_file}")
    print(f"Archivo: {Path(__file__).resolve()}")
    print("=" * 70)

    return 0


async def extraer_producto_directo(url, headless=True, timeout_ms=60000):
    return await extraer_producto(url, headless=headless, timeout_ms=timeout_ms)


if __name__ == "__main__":
    sys.exit(main())
