#!/usr/bin/env python3
import argparse
import hashlib
import html
import json
import os
import re
import subprocess
import sys
import time
import unicodedata
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from supabase import create_client
from sentence_transformers import SentenceTransformer

try:
    import fitz
except ImportError:
    try:
        import pymupdf as fitz
    except ImportError:
        fitz = None

try:
    import pdfplumber
except ImportError:
    pdfplumber = None

try:
    from langchain_text_splitters import RecursiveCharacterTextSplitter
except ImportError:
    RecursiveCharacterTextSplitter = None

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")
TABLA = "coach_otec"
MODELO_EMBEDDINGS = "intfloat/multilingual-e5-small"
LOTE_INSERCION = 50
LOTE_EMBEDDINGS = 32

CARPETAS_DEFAULT = (
    "/home/ibar/Documentos/Conocimiento/06_OS10_SENCE/CERTIFICACION",
    "/home/ibar/Documentos/Conocimiento/06_OS10_SENCE/OS10_REQUISITOS",
)

EXTENSIONES = {
    ".pdf", ".xlsx", ".xls", ".xlsm", ".csv",
    ".txt", ".md", ".json", ".docx", ".doc", ".pptx",
    ".odt", ".ods",
}

CARPETAS_EXCLUIDAS = {
    "1) adm no cursos",
    "alumnos",
    "docentes",
    "logos",
    "recursos tecnologicos",
    "facturas",
    "_otros",
    "oc",
}

PATRON_EXCLUIR_ARCHIVO = re.compile(
    r"(factura|balance|tributari|boleta|nota[_ -]?de[_ -]?credito|"
    r"libro[_ -]?diario|remuneracion|nomina|curriculum|e-?rut|"
    r"certificado[_ -]?bancario|carpeta[_ -]?tributaria|\biva\b)"
)

PATRONES_OTEC = {
    "certificacion": (
        re.compile(r"\bcertificados?\b"),
        re.compile(r"\bcertificaciones?\b"),
        re.compile(r"\bevaluaciones?\b"),
        re.compile(r"\bcuestionarios?\b"),
        re.compile(r"\bexamen(?:es)?\b"),
        re.compile(r"\bcalificaci[oó]n\b"),
        re.compile(r"\bconvalidaci[oó]n\b"),
        re.compile(r"\baprobaci[oó]n\b"),
    ),
    "os10": (
        re.compile(r"\bos\s*10\b"),
        re.compile(r"\bos10\b"),
        re.compile(r"\boperaci[oó]n\b"),
        re.compile(r"\bseguridad privada\b"),
        re.compile(r"\bclave ?única\b"),
    ),
    "legal": (
        re.compile(r"\bleyes?\b"),
        re.compile(r"\bdecretos?\b"),
        re.compile(r"\bdecreto\s+supremo\b"),
        re.compile(r"\bresoluci[oó]n(?:es)?\b"),
        re.compile(r"\bcircular(?:es)?\b"),
        re.compile(r"\breglamento(?:s)?\b"),
        re.compile(r"\bestatuto(?:s)?\b"),
        re.compile(r"\bnormativas?\b"),
        re.compile(r"\bcodigo del trabajo\b"),
        re.compile(r"\bministerio del trabajo\b"),
        re.compile(r"\bsubsecretaria\b"),
    ),
    "proceso": (
        re.compile(r"\bprocedimientos?\b"),
        re.compile(r"\binstructivos?\b"),
        re.compile(r"\bsolicitud(?:es)?\b"),
        re.compile(r"\bpostulaci[oó]n(?:es)?\b"),
        re.compile(r"\btramites?\b"),
        re.compile(r"\bpasos?\b"),
        re.compile(r"\bpresentar\b"),
        re.compile(r"\badjuntar\b"),
        re.compile(r"\bdocumentos requeridos\b"),
        re.compile(r"\bplazos?\b"),
        re.compile(r"\bchecklist\b"),
        re.compile(r"\bconvocatoria\b"),
    ),
}

TIPOS_OTEC = ("certificacion", "os10", "legal", "proceso")


def _normalizar(texto):
    descompuesto = unicodedata.normalize("NFKD", str(texto or ""))
    sin_acentos = "".join(c for c in descompuesto if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", sin_acentos).lower().strip()


def _contar(texto, patrones):
    total = sum(len(patron.findall(texto)) for patron in patrones)
    return min(total, 6)


def _ruta_excluida(ruta):
    partes = {_normalizar(parte) for parte in ruta.parts}
    if partes & CARPETAS_EXCLUIDAS:
        return True
    return bool(PATRON_EXCLUIR_ARCHIVO.search(_normalizar(ruta.name)))


def clasificar_fragmento(texto, ruta):
    contenido = _normalizar(texto)
    ruta_norm = _normalizar(str(ruta))
    puntajes = {
        tipo: _contar(contenido, patrones)
        for tipo, patrones in PATRONES_OTEC.items()
    }
    puntajes["legal"] += min(_contar(contenido, PATRONES_OTEC["legal"]), 1)

    if "certificacion" in ruta_norm:
        puntajes["certificacion"] += 3
    if "os10" in ruta_norm:
        puntajes["os10"] += 3
    if any(clave in ruta_norm for clave in ("ley", "decreto", "resolucion", "circular", "normativa", "reglamento", "legal")):
        puntajes["legal"] += 3
    if any(clave in ruta_norm for clave in ("proceso", "checklist", "solicitud", "instructivo", "tramite", "procedimiento", "postulacion")):
        puntajes["proceso"] += 3

    maximo = max(puntajes.values())
    if maximo <= 0:
        if "certificacion" in ruta_norm:
            return "certificacion"
        if "os10" in ruta_norm:
            return "os10"
        if "legal" in ruta_norm:
            return "legal"
        if "proceso" in ruta_norm:
            return "proceso"
        return None

    for tipo in TIPOS_OTEC:
        if puntajes[tipo] == maximo:
            return tipo
    return None


def extraer_texto(ruta):
    sufijo = ruta.suffix.lower()
    try:
        if not sufijo:
            return ruta.read_text(encoding="utf-8", errors="replace")

        if sufijo == ".pdf":
            if fitz is not None:
                with fitz.open(str(ruta)) as documento:
                    return "\n".join(pagina.get_text("text") for pagina in documento)
            if pdfplumber is not None:
                with pdfplumber.open(str(ruta)) as documento:
                    return "\n".join(pagina.extract_text() or "" for pagina in documento.pages)
            raise RuntimeError("Instala PyMuPDF o pdfplumber para leer PDFs.")

        if sufijo in {".xlsx", ".xls", ".xlsm"}:
            hojas = pd.read_excel(ruta, sheet_name=None, dtype=str)
            return "\n\n".join(
                f"### HOJA: {nombre}\n{tabla.fillna('').to_csv(index=False)}"
                for nombre, tabla in hojas.items()
            )

        if sufijo == ".csv":
            tabla = pd.read_csv(ruta, dtype=str)
            return tabla.fillna("").to_csv(index=False)

        if sufijo in {".txt", ".md", ".json"}:
            return ruta.read_text(encoding="utf-8", errors="replace")

        if sufijo == ".docx":
            return "\n\n".join(
                texto for texto, _ in extraer_bloques_docx(ruta)
            )

        if sufijo == ".doc":
            resultado = subprocess.run(
                ["catdoc", "-w", str(ruta)],
                capture_output=True,
                text=True,
                timeout=120,
            )
            return resultado.stdout if resultado.returncode == 0 else ""

        if sufijo in {".odt", ".ods"}:
            with zipfile.ZipFile(ruta) as archivo:
                xml = archivo.read("content.xml").decode("utf-8", errors="replace")
            texto = re.sub(r"<[^>]+>", " ", xml)
            return re.sub(r"\s+", " ", html.unescape(texto))

        if sufijo == ".pptx":
            from pptx import Presentation

            presentacion = Presentation(ruta)
            partes = []
            for diapositiva in presentacion.slides:
                for forma in diapositiva.shapes:
                    if hasattr(forma, "text") and forma.text.strip():
                        partes.append(forma.text)
            return "\n".join(partes)
    except Exception as error:
        print(f"    [ERROR] No se pudo leer {ruta.name}: {str(error)[:160]}")
        return ""

    return ""


def dividir_texto(texto, chunk_size=1200):
    # Splitter que preserva tablas: no corta bloques (\\n\\n) ni filas (\\n) por la mitad.
    # Cada fila de tabla viaja completa en un chunk (si cabe en chunk_size).
    if not texto or not texto.strip():
        return []
    bloques = [b.strip() for b in re.split(r"\n\s*\n", texto) if b.strip()]
    chunks, actual = [], ""
    for bloque in bloques:
        # Bloque muy largo: partir por líneas sin cortar filas
        if len(bloque) > chunk_size:
            for linea in bloque.split("\n"):
                linea = linea.strip()
                if not linea:
                    continue
                if len(linea) > chunk_size:
                    # Último recurso: solo partir esta línea larga
                    if RecursiveCharacterTextSplitter is not None:
                        divisor = RecursiveCharacterTextSplitter(
                            chunk_size=chunk_size, chunk_overlap=0,
                            separators=[". ", " ", ""],
                        )
                        chunks.extend(divisor.split_text(linea))
                    else:
                        chunks.extend(linea[i:i + chunk_size] for i in range(0, len(linea), chunk_size))
                elif len(actual) + 2 + len(linea) <= chunk_size:
                    actual = f"{actual}\n{linea}" if actual else linea
                else:
                    if actual:
                        chunks.append(actual)
                    actual = linea
            continue
        if len(actual) + 2 + len(bloque) <= chunk_size:
            actual = f"{actual}\n\n{bloque}" if actual else bloque
        else:
            if actual:
                chunks.append(actual)
            actual = bloque
    if actual:
        chunks.append(actual)
    return [c for c in chunks if c.strip()]


def _iter_bloques_docx(documento):
    from docx.oxml.ns import qn
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    for hijo in documento.element.body.iterchildren():
        if hijo.tag == qn("w:p"):
            yield Paragraph(hijo, documento)
        elif hijo.tag == qn("w:tbl"):
            yield Table(hijo, documento)


def _texto_tabla(tabla):
    filas = []
    for fila in tabla.rows:
        celdas = []
        for celda in fila.cells:
            valor = " ".join(celda.text.split())
            # Colapsa celdas combinadas que python-docx repite.
            if valor and (not celdas or celdas[-1] != valor):
                celdas.append(valor)
        texto_fila = " | ".join(celdas)
        if texto_fila.strip(" |"):
            filas.append(texto_fila)
    return "\n".join(filas).strip()


def extraer_bloques_docx(ruta):
    """Devuelve bloques (texto, es_tabla) en el orden real del DOCX.

    Cada tabla se entrega completa en un solo bloque para que el fragmentador
    no la corte; los parrafos se agrupan y luego pasan por dividir_texto().
    """
    import docx
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    documento = docx.Document(ruta)
    bloques = []
    parrafos = []

    def vaciar_parrafos():
        if parrafos:
            texto = "\n".join(parrafos).strip()
            if texto:
                bloques.append((texto, False))
            parrafos.clear()

    for bloque in _iter_bloques_docx(documento):
        if isinstance(bloque, Paragraph):
            if bloque.text.strip():
                parrafos.append(bloque.text.strip())
        elif isinstance(bloque, Table):
            vaciar_parrafos()
            texto_tabla = _texto_tabla(bloque)
            if texto_tabla:
                bloques.append((f"Documento: {ruta.name}\n{texto_tabla}", True))

    vaciar_parrafos()
    return bloques


def dividir_documento(ruta):
    """Fragmenta prosa, pero mantiene cada tabla DOCX como bloque entero."""
    if ruta.suffix.lower() == ".docx":
        chunks = []
        for texto, es_tabla in extraer_bloques_docx(ruta):
            if es_tabla:
                chunks.append(texto)
            else:
                chunks.extend(dividir_texto(texto))
        return chunks
    return dividir_texto(extraer_texto(ruta))


def generar_hash(texto):
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def cargar_hashes(cliente, tabla):
    hashes = set()
    inicio = 0
    while True:
        respuesta = (
            cliente.table(tabla)
            .select("hash_origen")
            .range(inicio, inicio + 999)
            .execute()
        )
        filas = respuesta.data or []
        hashes.update(
            fila["hash_origen"] for fila in filas if fila.get("hash_origen")
        )
        if len(filas) < 1000:
            break
        inicio += 1000
    return hashes


def limpiar_tabla(cliente, tabla):
    cliente.table(tabla).delete().neq("id", 0).execute()
    print(f"  Tabla {tabla} limpiada antes de la ingesta.")


def borrar_por_archivo(cliente, tabla, nombre_archivo):
    # Borra fragmentos previos de un archivo (metadata->>archivo) antes de reingestar
    res = (
        cliente.table(tabla)
        .select("id")
        .filter("metadata->>archivo", "eq", nombre_archivo)
        .execute()
    )
    ids = [fila["id"] for fila in (res.data or [])]
    for id_ in ids:
        cliente.table(tabla).delete().eq("id", id_).execute()
    print(f"  Borrados {len(ids)} fragmentos previos de {nombre_archivo}.")
    return len(ids)


def insertar_lote(cliente, tabla, lote):
    try:
        cliente.table(tabla).insert(lote).execute()
        return len(lote), 0
    except Exception as error:
        print(f"    [WARN] Falló lote de {len(lote)}; reintentando uno a uno: {str(error)[:120]}")
        insertados = 0
        errores = 0
        for fila in lote:
            try:
                cliente.table(tabla).insert(fila).execute()
                insertados += 1
            except Exception as error_fila:
                errores += 1
                print(f"      [ERROR] {str(error_fila)[:120]}")
        return insertados, errores


def _parece_texto(ruta):
    try:
        muestra = ruta.read_bytes()[:2048]
        return b"\x00" not in muestra
    except OSError:
        return False


def listar_archivos(carpetas, max_archivos=None):
    archivos = []
    for carpeta in carpetas:
        ruta_carpeta = Path(carpeta).expanduser()
        if not ruta_carpeta.is_dir():
            print(f"[WARN] No existe la carpeta: {ruta_carpeta}")
            continue
        for ruta in ruta_carpeta.rglob("*"):
            if not ruta.is_file():
                continue
            sufijo = ruta.suffix.lower()
            if sufijo not in EXTENSIONES and (sufijo or not _parece_texto(ruta)):
                continue
            if _ruta_excluida(ruta):
                continue
            archivos.append(ruta.resolve())

    archivos = sorted(set(archivos))
    if max_archivos is not None:
        archivos = archivos[:max_archivos]
    return archivos


def main():
    parser = argparse.ArgumentParser(description="Ingesta OTEC hacia coach_otec.")
    parser.add_argument(
        "--carpetas",
        nargs="+",
        default=list(CARPETAS_DEFAULT),
        help="Carpetas a procesar.",
    )
    parser.add_argument("--limpiar", action="store_true", help="Borrar coach_otec antes de insertar.")
    parser.add_argument("--dry-run", action="store_true", help="Simular sin escribir en Supabase.")
    parser.add_argument("--max-archivos", type=int, default=None, help="Limitar cantidad de archivos.")
    parser.add_argument("--lote-embeddings", type=int, default=LOTE_EMBEDDINGS, help="Tamaño de lote para embeddings.")
    parser.add_argument("--archivo", type=str, default=None, help="Reingestar solo este archivo (ej. F-248).")
    parser.add_argument("--borrar-archivo", action="store_true", help="Borrar fragmentos previos de --archivo antes de insertar.")
    args = parser.parse_args()

    if args.archivo:
        ruta_sola = Path(args.archivo).expanduser()
        if not ruta_sola.is_file():
            # Permitir pasar solo el nombre del archivo dentro de las carpetas default
            candidatos = [
                r for r in listar_archivos(args.carpetas, None)
                if r.name == ruta_sola.name or r.name == args.archivo or args.archivo in str(r)
            ]
            if not candidatos:
                print(f"[ERROR] No se encontró --archivo {args.archivo}")
                return
            archivos = candidatos
        else:
            archivos = [ruta_sola.resolve()]
    else:
        archivos = listar_archivos(args.carpetas, args.max_archivos)
    if not archivos:
        print("[ERROR] No se encontraron archivos para procesar.")
        return

    print(f"📁 {len(archivos)} archivo(s) encontrado(s).")

    if args.dry_run:
        stats = {"certificacion": 0, "os10": 0, "legal": 0, "proceso": 0, "omitidos": 0, "archivos": 0}
        for ruta in archivos:
            chunks = dividir_documento(ruta)
            if not chunks:
                stats["omitidos"] += 1
                continue
            stats["archivos"] += 1
            for chunk in chunks:
                if len(chunk.strip()) < 100:
                    continue
                tipo = clasificar_fragmento(chunk, ruta)
                if tipo:
                    stats[tipo] += 1
                else:
                    stats["omitidos"] += 1
        print(
            f"  DRY-RUN: certificacion={stats['certificacion']} os10={stats['os10']} "
            f"legal={stats['legal']} proceso={stats['proceso']} omitidos={stats['omitidos']} "
            f"archivos_con_texto={stats['archivos']}"
        )
        return

    if not SUPABASE_URL or not SUPABASE_KEY:
        print("[ERROR] Faltan SUPABASE_URL y SUPABASE_SERVICE_ROLE_KEY en el .env")
        sys.exit(1)

    cliente = create_client(SUPABASE_URL, SUPABASE_KEY)
    if args.limpiar:
        limpiar_tabla(cliente, TABLA)
    if args.borrar_archivo and args.archivo and archivos:
        borrar_por_archivo(cliente, TABLA, archivos[0].name)

    hashes_existentes = cargar_hashes(cliente, TABLA)
    print(f"  Hashes existentes en {TABLA}: {len(hashes_existentes)}")

    print("  Cargando modelo de embeddings...")
    modelo = SentenceTransformer(MODELO_EMBEDDINGS)

    stats = {
        "insertados": 0,
        "duplicados": 0,
        "errores": 0,
        "omitidos": 0,
        "certificacion": 0,
        "os10": 0,
        "legal": 0,
        "proceso": 0,
        "archivos": 0,
    }

    for ruta in archivos:
        print(f"  Procesando: {ruta.name}")
        chunks = dividir_documento(ruta)
        if not chunks:
            print("    [WARN] Archivo vacío o sin texto extraíble.")
            continue

        stats["archivos"] += 1
        pendientes = []
        ruta_norm = _normalizar(str(ruta))
        fuente = "certificacion" if "certificacion" in ruta_norm else "os10"

        for chunk in chunks:
            if len(chunk.strip()) < 100:
                continue
            hash_txt = generar_hash(chunk)
            if hash_txt in hashes_existentes:
                stats["duplicados"] += 1
                continue
            tipo = clasificar_fragmento(chunk, ruta)
            if not tipo:
                stats["omitidos"] += 1
                continue
            hashes_existentes.add(hash_txt)
            pendientes.append((hash_txt, chunk, tipo))

        insertados_archivo = 0
        errores_archivo = 0
        for inicio in range(0, len(pendientes), args.lote_embeddings):
            grupo = pendientes[inicio:inicio + args.lote_embeddings]
            vectores = modelo.encode(
                [f"passage: {chunk}" for _, chunk, _ in grupo],
                batch_size=args.lote_embeddings,
                show_progress_bar=False,
            )
            lote = []
            for (hash_txt, chunk, tipo), vector in zip(grupo, vectores):
                metadata = {
                    "tema": "otec",
                    "tipo": tipo,
                    "archivo": ruta.name,
                    "ruta": str(ruta),
                    "fuente": fuente,
                }
                lote.append(
                    {
                        "contenido": chunk,
                        "metadata": metadata,
                        "embedding": vector.tolist(),
                        "hash_origen": hash_txt,
                    }
                )
                stats[tipo] += 1
                if len(lote) >= LOTE_INSERCION:
                    insertados, errores = insertar_lote(cliente, TABLA, lote)
                    insertados_archivo += insertados
                    errores_archivo += errores
                    lote.clear()
            if lote:
                insertados, errores = insertar_lote(cliente, TABLA, lote)
                insertados_archivo += insertados
                errores_archivo += errores

        stats["insertados"] += insertados_archivo
        stats["errores"] += errores_archivo
        print(
            f"    {len(chunks)} fragmentos: {insertados_archivo} insertados, "
            f"{errores_archivo} errores."
        )

    print("\n" + "=" * 50)
    print("📊 RESUMEN DE INGESTA OTEC")
    print("=" * 50)
    print(f"  Archivos con texto:       {stats['archivos']}")
    print(f"  Insertados en {TABLA}: {stats['insertados']}")
    print(f"  Certificación:            {stats['certificacion']}")
    print(f"  OS10:                      {stats['os10']}")
    print(f"  Legal:                     {stats['legal']}")
    print(f"  Proceso:                   {stats['proceso']}")
    print(f"  Duplicados omitidos:      {stats['duplicados']}")
    print(f"  Fragmentos no clasificados: {stats['omitidos']}")
    print(f"  Errores:                  {stats['errores']}")
    print("=" * 50)


if __name__ == "__main__":
    main()
