#!/usr/bin/env python3
import argparse
import hashlib
import html
import os
import re
import subprocess
import sys
import unicodedata
import zipfile
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
TABLA = "coach_sence"
MODELO_EMBEDDINGS = "intfloat/multilingual-e5-small"
LOTE_INSERCION = 50
LOTE_EMBEDDINGS = 32

CARPETAS_DEFAULT = (
    "/home/ibar/Documentos/Conocimiento/OS10_SENCE",
    "/home/ibar/ARCHIVO/Escritorio/1) Zengin Otec/Docs Sence",
    "/home/ibar/ARCHIVO/Escritorio/1) Zengin Otec/OS10",
    "/home/ibar/ARCHIVO/Escritorio/1) Zengin Otec/2) Cursos/Cursos a realizar",
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

PATRONES_CURSO = tuple(
    re.compile(patron)
    for patron in (
        r"\bcursos?\b",
        r"\bcapacitacion(?:es)?\b",
        r"\brelator(?:a|es)?\b",
        r"\bfacilitador(?:a|es)?\b",
        r"\bparticipantes?\b",
        r"\balumnos?\b",
        r"\bmodulos?\b",
        r"\bsesion(?:es)?\b",
        r"\bclases?\b",
        r"\bhoras?\b",
        r"\bpresencial\b",
        r"\be-?learning\b",
        r"\bsincronic[oa]\b",
        r"\basincronic[oa]\b",
        r"\bdiploma\b",
        r"\bcertificados?\b",
        r"\bevaluacion(?:es)?\b",
        r"\bmaterial(?:es)? didactic[oa]s?\b",
        r"\bapuntes?\b",
        r"\bprecios?\b",
        r"\barancel(?:es)?\b",
        r"\bmatricula\b",
        r"\binscripcion(?:es)?\b",
        r"\buf\b",
        r"\butm\b",
        r"\$\s?\d",
        r"\bcod(?:igo)?\.?\s*sence\b",
        r"\bsence\b[^\n]{0,50}\b\d{6,12}\b",
        r"\b\d{6,12}\b[^\n]{0,50}\bsence\b",
    )
)

PATRONES_NORMATIVA = tuple(
    re.compile(patron)
    for patron in (
        r"\bleyes?\b",
        r"\bdecretos?\b",
        r"\bd\.?\s*s\.?\s*n?[°º]?\s*\d+",
        r"\bresolucion(?:es)?\b",
        r"\bres\.?\s*ex(?:enta)?\.?\b",
        r"\bcircular(?:es)?\b",
        r"\breglamentos?\b",
        r"\bestatutos?\b",
        r"\barticulos?\b",
        r"\bnormativas?\b",
        r"\bcodigo del trabajo\b",
        r"\bseguridad privada\b",
        r"\bdirectemar\b",
        r"\bos10\b",
        r"\bministerio del trabajo\b",
        r"\bsubsecretaria\b",
        r"\brequisitos?\b",
        r"\bobligacion(?:es)?\b",
    )
)

PATRONES_TRAMITE = tuple(
    re.compile(patron)
    for patron in (
        r"\bformularios?\b",
        r"\binstructivos?\b",
        r"\bsolicitud(?:es)?\b",
        r"\bpostulacion(?:es)?\b",
        r"\bpostular\b",
        r"\btramites?\b",
        r"\bpasos?\b",
        r"\bpresentar\b",
        r"\badjuntar\b",
        r"\bdocumentos requeridos\b",
        r"\bplazos?\b",
        r"\bportal\b",
        r"\bplataforma\b",
        r"\bfranquicia\b",
        r"\bactualizacion de costos\b",
        r"\bacreditacion\b",
        r"\bregistro\b",
        r"\bconvocatoria\b",
        r"\bcalendario\b",
    )
)

PATRONES_OTEC = tuple(
    re.compile(patron)
    for patron in (
        r"\botec\b",
        r"\botic\b",
        r"\bsence\b",
    )
)


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
        "curso": _contar(contenido, PATRONES_CURSO) * 2,
        "normativa": _contar(contenido, PATRONES_NORMATIVA) * 2,
        "tramite": _contar(contenido, PATRONES_TRAMITE) * 2,
    }
    puntajes["normativa"] += min(_contar(contenido, PATRONES_OTEC), 1)

    if "curso" in ruta_norm:
        puntajes["curso"] += 3
    if any(clave in ruta_norm for clave in ("formulario", "instructivo", "solicitud", "postulacion", "tramite")):
        puntajes["tramite"] += 3
    if any(clave in ruta_norm for clave in ("ley", "decreto", "resolucion", "circular", "normativa", "reglamento")):
        puntajes["normativa"] += 3
    if any(clave in ruta_norm for clave in ("os10", "seguridad privada", "directemar")):
        puntajes["normativa"] += 2

    maximo = max(puntajes.values())
    if maximo <= 0:
        if "curso" in ruta_norm:
            return "curso"
        if "docs sence" in ruta_norm:
            return "tramite"
        if any(clave in ruta_norm for clave in ("os10", "seguridad", "normativa")):
            return "normativa"
        return None

    for tipo in ("tramite", "curso", "normativa"):
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
            import docx

            documento = docx.Document(ruta)
            partes = [p.text for p in documento.paragraphs if p.text.strip()]
            for tabla in documento.tables:
                for fila in tabla.rows:
                    partes.append(" | ".join(celda.text.strip() for celda in fila.cells))
            return "\n".join(partes)

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


def dividir_texto(texto):
    if RecursiveCharacterTextSplitter is None:
        return [
            texto[i:i + 1000]
            for i in range(0, len(texto), 1000)
            if texto[i:i + 1000].strip()
        ]
    divisor = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=150,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    return divisor.split_text(texto)


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
    parser = argparse.ArgumentParser(description="Ingesta OTEC/SENCE (Zengin) hacia coach_sence.")
    parser.add_argument(
        "--carpetas",
        nargs="+",
        default=list(CARPETAS_DEFAULT),
        help="Carpetas a procesar.",
    )
    parser.add_argument("--limpiar", action="store_true", help="Borrar coach_sence antes de insertar.")
    parser.add_argument("--dry-run", action="store_true", help="Simular sin escribir en Supabase.")
    parser.add_argument("--max-archivos", type=int, default=None, help="Limitar cantidad de archivos.")
    parser.add_argument("--lote-embeddings", type=int, default=LOTE_EMBEDDINGS, help="Tamaño de lote para embeddings.")
    args = parser.parse_args()

    archivos = listar_archivos(args.carpetas, args.max_archivos)
    if not archivos:
        print("[ERROR] No se encontraron archivos para procesar.")
        return

    print(f"📁 {len(archivos)} archivo(s) encontrado(s).")

    if args.dry_run:
        stats = {"curso": 0, "normativa": 0, "tramite": 0, "omitidos": 0, "archivos": 0}
        for ruta in archivos:
            texto = extraer_texto(ruta)
            if not texto.strip():
                stats["omitidos"] += 1
                continue
            stats["archivos"] += 1
            for chunk in dividir_texto(texto):
                if len(chunk.strip()) < 100:
                    continue
                tipo = clasificar_fragmento(chunk, ruta)
                if tipo:
                    stats[tipo] += 1
                else:
                    stats["omitidos"] += 1
        print(
            f"  DRY-RUN: curso={stats['curso']} normativa={stats['normativa']} "
            f"tramite={stats['tramite']} omitidos={stats['omitidos']} "
            f"archivos_con_texto={stats['archivos']}"
        )
        return

    if not SUPABASE_URL or not SUPABASE_KEY:
        print("[ERROR] Faltan SUPABASE_URL y SUPABASE_SERVICE_ROLE_KEY en el .env")
        sys.exit(1)

    cliente = create_client(SUPABASE_URL, SUPABASE_KEY)
    if args.limpiar:
        limpiar_tabla(cliente, TABLA)

    hashes_existentes = cargar_hashes(cliente, TABLA)
    print(f"  Hashes existentes en {TABLA}: {len(hashes_existentes)}")

    print("  Cargando modelo de embeddings...")
    modelo = SentenceTransformer(MODELO_EMBEDDINGS)

    stats = {
        "insertados": 0,
        "duplicados": 0,
        "errores": 0,
        "omitidos": 0,
        "curso": 0,
        "normativa": 0,
        "tramite": 0,
        "archivos": 0,
    }

    for ruta in archivos:
        print(f"  Procesando: {ruta.name}")
        texto = extraer_texto(ruta)
        if not texto.strip():
            print("    [WARN] Archivo vacío o sin texto extraíble.")
            continue

        stats["archivos"] += 1
        chunks = dividir_texto(texto)
        pendientes = []

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
                    "tema": "sence",
                    "tipo": tipo,
                    "archivo": ruta.name,
                    "ruta": str(ruta),
                    "fuente": "zengin" if "zengin" in _normalizar(str(ruta)) else "os10",
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
    print("📊 RESUMEN DE INGESTA SENCE")
    print("=" * 50)
    print(f"  Archivos con texto:       {stats['archivos']}")
    print(f"  Insertados en {TABLA}: {stats['insertados']}")
    print(f"  Curso:                    {stats['curso']}")
    print(f"  Normativa:                {stats['normativa']}")
    print(f"  Trámite:                  {stats['tramite']}")
    print(f"  Duplicados omitidos:      {stats['duplicados']}")
    print(f"  Fragmentos no clasificados: {stats['omitidos']}")
    print(f"  Errores:                  {stats['errores']}")
    print("=" * 50)


if __name__ == "__main__":
    main()
