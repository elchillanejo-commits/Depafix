"""Generador de afiches para el agente Ikki."""

import os
from datetime import datetime

from PIL import Image, ImageDraw, ImageFont

ANCHO, ALTO = 1080, 1350
DIR_SALIDA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "afiches")

FUENTES_CANDIDATAS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]


def _cargar_fuente(tamano, negrita=True):
    for ruta in FUENTES_CANDIDATAS:
        if negrita and "Bold" not in ruta:
            continue
        if os.path.exists(ruta):
            return ImageFont.truetype(ruta, tamano)
    for ruta in FUENTES_CANDIDATAS:
        if os.path.exists(ruta):
            return ImageFont.truetype(ruta, tamano)
    return ImageFont.load_default()


def _envolver_texto(draw, texto, fuente, ancho_max):
    palabras = texto.split()
    lineas = []
    actual = ""
    for palabra in palabras:
        prueba = f"{actual} {palabra}".strip()
        caja = draw.textbbox((0, 0), prueba, font=fuente)
        if caja[2] - caja[0] <= ancho_max or not actual:
            actual = prueba
        else:
            lineas.append(actual)
            actual = palabra
    if actual:
        lineas.append(actual)
    return lineas


def _dibujar_texto_centrado(draw, y, texto, fuente, color, ancho_max):
    lineas = _envolver_texto(draw, texto, fuente, ancho_max)
    for linea in lineas:
        caja = draw.textbbox((0, 0), linea, font=fuente)
        w = caja[2] - caja[0]
        h = caja[3] - caja[1]
        x = (ANCHO - w) / 2
        draw.text((x, y), linea, font=fuente, fill=color)
        y += h + 14
    return y


def generar_afiche(datos):
    """
    Genera un afiche a partir de un dict con:
      - titulo (str, requerido)
      - subtitulo (str, opcional)
      - precio (str, opcional)
      - imagen_fondo (str, opcional): ruta a una imagen de fondo
      - logo (str | "circulo", opcional): ruta a un logo, o "circulo" para un logo genérico
      - colores (dict, opcional): {"fondo": "#RRGGBB", "titulo": "#RRGGBB",
                                    "subtitulo": "#RRGGBB", "precio": "#RRGGBB", "acento": "#RRGGBB"}
    Retorna la ruta del archivo .png generado.
    """
    titulo = datos.get("titulo", "")
    subtitulo = datos.get("subtitulo", "")
    precio = datos.get("precio", "")
    imagen_fondo = datos.get("imagen_fondo")
    logo = datos.get("logo")
    colores = datos.get("colores") or {}

    color_fondo = colores.get("fondo", "#1E3A5F")
    color_titulo = colores.get("titulo", "#FFFFFF")
    color_subtitulo = colores.get("subtitulo", "#D9E4EC")
    color_precio = colores.get("precio", "#FFC857")
    color_acento = colores.get("acento", "#FFC857")

    if imagen_fondo and os.path.exists(imagen_fondo):
        img = Image.open(imagen_fondo).convert("RGB").resize((ANCHO, ALTO))
        overlay = Image.new("RGBA", (ANCHO, ALTO), (0, 0, 0, 120))
        img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    else:
        img = Image.new("RGB", (ANCHO, ALTO), color_fondo)

    draw = ImageDraw.Draw(img)
    margen = 80
    ancho_texto = ANCHO - 2 * margen

    draw.rectangle([0, 0, ANCHO, 16], fill=color_acento)
    draw.rectangle([0, ALTO - 16, ANCHO, ALTO], fill=color_acento)

    if logo == "circulo":
        r = 70
        cx, cy = ANCHO // 2, 170
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color_acento)
    elif logo and os.path.exists(logo):
        logo_img = Image.open(logo).convert("RGBA")
        logo_img.thumbnail((160, 160))
        pos = ((ANCHO - logo_img.width) // 2, 100)
        img.paste(logo_img, pos, logo_img)

    y = 320
    fuente_titulo = _cargar_fuente(72, negrita=True)
    y = _dibujar_texto_centrado(draw, y, titulo, fuente_titulo, color_titulo, ancho_texto)

    if subtitulo:
        y += 20
        fuente_subtitulo = _cargar_fuente(42, negrita=False)
        y = _dibujar_texto_centrado(draw, y, subtitulo, fuente_subtitulo, color_subtitulo, ancho_texto)

    if precio:
        fuente_precio = _cargar_fuente(90, negrita=True)
        caja = draw.textbbox((0, 0), precio, font=fuente_precio)
        w = caja[2] - caja[0]
        h = caja[3] - caja[1]
        px = (ANCHO - w) / 2
        py = ALTO - 300
        pad_x, pad_y = 40, 24
        draw.rounded_rectangle(
            [px - pad_x, py - pad_y, px + w + pad_x, py + h + pad_y],
            radius=20,
            fill=color_acento,
        )
        draw.text((px, py), precio, font=fuente_precio, fill="#1E1E1E")

    os.makedirs(DIR_SALIDA, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    nombre_archivo = f"afiche_{timestamp}.png"
    ruta_salida = os.path.join(DIR_SALIDA, nombre_archivo)
    img.save(ruta_salida, "PNG")

    return ruta_salida


if __name__ == "__main__":
    ruta = generar_afiche(
        {
            "titulo": "¡Oferta Especial!",
            "subtitulo": "Construcción con 50% de descuento",
            "precio": "$1.500.000",
            "logo": "circulo",
        }
    )
    print(ruta)
