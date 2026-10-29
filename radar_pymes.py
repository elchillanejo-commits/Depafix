import argparse
import os
import re
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup


CARPETA_SALIDA = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "logs", "analisis_web"
)
TIMEOUT = 20
MAX_CARACTERES = 2000


def analizar_url(url):
    try:
        respuesta = requests.get(
            url,
            timeout=TIMEOUT,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (X11; Linux x86_64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0 Safari/537.36"
                )
            },
        )
        respuesta.raise_for_status()

        soup = BeautifulSoup(respuesta.text, "html.parser")
        titulo = soup.title.get_text(" ", strip=True) if soup.title else "Sin título"

        meta_descripcion = soup.find("meta", attrs={"name": "description"})
        descripcion = (
            meta_descripcion.get("content", "").strip()
            if meta_descripcion
            else "Sin descripción"
        )

        for elemento in soup(["script", "style", "noscript"]):
            elemento.decompose()

        texto_visible = soup.get_text(" ", strip=True)
        texto_visible = re.sub(r"\s+", " ", texto_visible)[:MAX_CARACTERES]

        dominio = urlparse(url).netloc.lower()
        if not dominio:
            raise ValueError("La URL no contiene un dominio válido")
        nombre_archivo = re.sub(r"[^a-z0-9.-]", "_", dominio) + ".txt"

        os.makedirs(CARPETA_SALIDA, exist_ok=True)
        ruta_salida = os.path.join(CARPETA_SALIDA, nombre_archivo)
        contenido = (
            f"URL: {url}\n"
            f"TÍTULO: {titulo}\n"
            f"DESCRIPCIÓN: {descripcion or 'Sin descripción'}\n\n"
            f"TEXTO VISIBLE (máximo {MAX_CARACTERES} caracteres):\n"
            f"{texto_visible}\n"
        )
        with open(ruta_salida, "w", encoding="utf-8") as archivo:
            archivo.write(contenido)

        print(f"✅ Guardado: {ruta_salida}")
    except Exception as error:
        print(f"⚠️ No se pudo analizar {url}: {error}")


def main():
    parser = argparse.ArgumentParser(
        description="Extrae información básica de webs o perfiles públicos."
    )
    parser.add_argument("urls", nargs="+", help="Lista de URLs separadas por espacios")
    args = parser.parse_args()

    for url in args.urls:
        analizar_url(url)


if __name__ == "__main__":
    main()
