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
MIN_CARACTERES = 500
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
    except requests.exceptions.Timeout:
        print(f"FALLIDA: {url} | Tiempo de espera agotado tras {TIMEOUT}s.")
        return False
    except requests.exceptions.SSLError as error:
        print(f"FALLIDA: {url} | Error de certificado SSL/TLS: {error}")
        return False
    except requests.exceptions.ConnectionError as error:
        print(f"FALLIDA: {url} | Error de red o conexión: {error}")
        return False
    except requests.exceptions.RequestException as error:
        print(f"FALLIDA: {url} | Petición no válida: {error}")
        return False

    try:
        respuesta.raise_for_status()
    except requests.exceptions.HTTPError as error:
        estado = error.response.status_code if error.response is not None else "desconocido"
        if estado == 403:
            print(
                f"FALLIDA: {url} | Acceso denegado (403). "
                "La web bloquea el scraping o requiere autenticación."
            )
        elif estado == 429:
            print(f"FALLIDA: {url} | Demasiadas peticiones (429).")
        else:
            print(f"FALLIDA: {url} | Error HTTP {estado}.")
        return False

    try:
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
        texto_visible = re.sub(r"\s+", " ", texto_visible)
        caracteres_extraidos = len(texto_visible)
        if caracteres_extraidos < MIN_CARACTERES:
            print(
                f"FALLIDA: {url} | Texto extraído insuficiente: "
                f"{caracteres_extraidos} caracteres (mínimo {MIN_CARACTERES})."
            )
            return False
        texto_visible = texto_visible[:MAX_CARACTERES]

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

        print(f"EXITOSA: {url} | Guardado: {ruta_salida}")
    except Exception as error:
        print(f"FALLIDA: {url} | No se pudo procesar el contenido: {error}")
        return False

    return True


def main():
    parser = argparse.ArgumentParser(
        description="Extrae información básica de webs o perfiles públicos."
    )
    parser.add_argument("urls", nargs="+", help="Lista de URLs separadas por espacios")
    args = parser.parse_args()

    fallidas = 0
    for url in args.urls:
        try:
            if not analizar_url(url):
                fallidas += 1
        except Exception as error:
            fallidas += 1
            print(f"FALLIDA: {url} | Error inesperado: {error}")

    if fallidas:
        print(f"Resumen: {fallidas} de {len(args.urls)} URL(s) fallida(s).")
        return 1 if fallidas == len(args.urls) else 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
