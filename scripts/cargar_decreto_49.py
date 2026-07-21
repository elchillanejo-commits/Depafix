#!/usr/bin/env python3
"""Carga D.S. N°49 desde PDF a Supabase (decretos/decreto_articulos/decreto_materiales)."""
import os
import re
import sys
import logging
from pathlib import Path
from datetime import datetime

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, "/home/ibar/Proyectos/02_PROCURADOR")  # reorg 2026-07-19: core/ movido fuera de DepaFix

import pdfplumber
from core.db_manager import DatabaseManager

PDF_PATH = Path(os.path.expanduser("~/Descargas/DS49.pdf"))
PDF_FALLBACK_LOCAL = REPO_ROOT / "01_SERVIU" / "docs" / "DS49_texto.pdf"
PDF_FALLBACK_URL = "https://www.minvu.gob.cl/wp-content/uploads/2019/05/DS-49_FSEV-texto-DS-105_2014_23jul20.pdf"
FECHA_PUBLICACION = "2012-04-26"  # no está en el cuerpo del texto; Diario Oficial vía BCN

LOG_PATH = REPO_ROOT / "logs" / "carga_ds49.log"
logging.basicConfig(
    filename=str(LOG_PATH), level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("carga_ds49")
_console = logging.StreamHandler()
_console.setFormatter(logging.Formatter("%(levelname)s - %(message)s"))
logger.addHandler(_console)

CABECERA_RE = re.compile(r"D\.?\s?S\.?\s*N[°ºo]\.?\s*(\d+),?\s*DE\s*(\d{4})", re.IGNORECASE)
ARTICULO_RE = re.compile(
    r"Art[íi]culo\s+(\d+)\.?\s*([^\n]*)\n(.*?)(?=\n\s*Art[íi]culo\s+\d+\.|\Z)", re.DOTALL,
)
MATERIAL_KEYWORDS = [
    "hormigón", "hormigon", "acero", "cemento", "árido", "arido", "grava", "arena",
    "ladrillo", "bloque", "cerámica", "ceramica", "pintura", "madera", "vidrio",
    "cobre", "plástico", "plastico", "asfalto", "yeso", "pvc", "fierro",
]


def _registrar_error(client, mensaje):
    logger.error(mensaje)
    try:
        client.table("error_logs").insert({
            "agente": "cargar_decreto_49",
            "error_msg": mensaje,
            "created_at": datetime.now().isoformat(),
        }).execute()
    except Exception as e:
        logger.error(f"No se pudo escribir en error_logs: {e}")


def resolver_pdf():
    if PDF_PATH.exists():
        return PDF_PATH
    if PDF_FALLBACK_LOCAL.exists():
        logger.info(f"No hay PDF en {PDF_PATH}, usando copia local {PDF_FALLBACK_LOCAL}")
        return PDF_FALLBACK_LOCAL
    logger.info(f"No hay PDF local, descargando desde {PDF_FALLBACK_URL}")
    import requests
    PDF_PATH.parent.mkdir(parents=True, exist_ok=True)
    resp = requests.get(PDF_FALLBACK_URL, stream=True, timeout=30)
    resp.raise_for_status()
    with open(PDF_PATH, "wb") as f:
        for chunk in resp.iter_content(8192):
            f.write(chunk)
    return PDF_PATH


def extraer_texto(pdf_path):
    with pdfplumber.open(str(pdf_path)) as pdf:
        return "\n".join(p.extract_text() or "" for p in pdf.pages)


def extraer_cabecera(texto):
    m = CABECERA_RE.search(texto)
    numero = m.group(1) if m else "49"
    titulo = ""
    if m:
        for linea in texto[m.end():].splitlines():
            linea = linea.strip()
            if linea:
                titulo = linea
                break
    return numero, titulo or "Decreto Supremo N°49"


def extraer_articulos(texto):
    return [
        {"numero": num.strip(), "contenido": f"{tit.strip()}\n{cuerpo.strip()}".strip()}
        for num, tit, cuerpo in ARTICULO_RE.findall(texto)
    ]


def extraer_materiales(contenido):
    low = contenido.lower()
    return sorted({m for m in MATERIAL_KEYWORDS if m in low})


def main():
    client = DatabaseManager.get_service_client()

    pdf_path = resolver_pdf()
    logger.info(f"Extrayendo texto de {pdf_path}")
    texto = extraer_texto(pdf_path)

    numero, titulo = extraer_cabecera(texto)
    articulos = extraer_articulos(texto)
    logger.info(f"Decreto N°{numero} - {len(articulos)} artículos detectados")

    stats = {"decretos": 0, "articulos": 0, "materiales": 0}

    try:
        result = client.table("decretos").upsert({
            "numero": numero,
            "titulo": titulo,
            "fecha_publicacion": FECHA_PUBLICACION,
            "url": PDF_FALLBACK_URL,
        }, on_conflict="numero").execute()
        decreto_id = result.data[0]["id"]
        stats["decretos"] = 1
    except Exception as e:
        _registrar_error(client, f"Error upsert decretos: {e}")
        sys.exit(1)

    for art in articulos:
        try:
            result = client.table("decreto_articulos").upsert({
                "decreto_id": decreto_id,
                "numero": art["numero"],
                "contenido": art["contenido"][:5000],
            }, on_conflict="decreto_id,numero").execute()
        except Exception as e:
            _registrar_error(client, f"Error artículo {art['numero']}: {e}")
            continue

        if not result.data:
            continue
        articulo_id = result.data[0]["id"]
        stats["articulos"] += 1

        for mat in extraer_materiales(art["contenido"]):
            existente = (
                client.table("decreto_materiales").select("id")
                .eq("articulo_id", articulo_id).eq("nombre_material", mat).execute()
            )
            if existente.data:
                continue
            try:
                client.table("decreto_materiales").insert({
                    "articulo_id": articulo_id,
                    "nombre_material": mat,
                    "codigo_unidad": None,  # no viene en el texto del decreto
                }).execute()
                stats["materiales"] += 1
            except Exception as e:
                _registrar_error(client, f"Error material '{mat}' art {art['numero']}: {e}")

    logger.info(
        f"✅ Decretos: {stats['decretos']} | Artículos: {stats['articulos']} | Materiales: {stats['materiales']}"
    )
    return stats


if __name__ == "__main__":
    main()
