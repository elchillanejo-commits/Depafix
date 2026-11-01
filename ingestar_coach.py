#!/usr/bin/env python3
import os
import sys
import hashlib
import argparse
import subprocess
from pathlib import Path
from dotenv import load_dotenv
from supabase import create_client
from langchain_text_splitters import RecursiveCharacterTextSplitter
from sentence_transformers import SentenceTransformer

load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("[ERROR] Faltan credenciales de Supabase en el .env")
    sys.exit(1)

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

CONOCIMIENTO_DIR = Path("/home/ibar/Documentos/Conocimiento")
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data" / "fusionados"
EXTENSIONES = {
    ".txt", ".md", ".pdf", ".csv",
    ".xlsx", ".xls", ".xlsm", ".docx", ".doc",
}
LOTE_INSERCION = 50

CONFIG_TEMAS = {
    "shopify": {"archivo": "conocimiento_shopify.txt", "tabla": "coach_shopify"},
    "rrss":    {"archivo": "conocimiento_rrss.txt",    "tabla": "coach_rrss"},
    "fuego":   {"archivo": "conocimiento_fuego.txt",   "tabla": "coach_python"},
    "tierra":  {"carpeta": CONOCIMIENTO_DIR / "Tierra_Construccion", "tabla": "coach_tierra"},
    "metal":   {"carpeta": CONOCIMIENTO_DIR / "Metal_Procurador",    "tabla": "coach_metal"},
    "sence":   {"archivo": "conocimiento_sence.txt",    "tabla": "coach_sence"},
    "os10":    {"carpeta": CONOCIMIENTO_DIR / "OS10_SENCE", "tabla": "coach_sence"},
}


def generar_hash(texto):
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def _hash_existe_directo(tabla, hash_origen):
    try:
        respuesta = (
            supabase.table(tabla)
            .select("id")
            .eq("hash_origen", hash_origen)
            .limit(1)
            .execute()
        )
        return len(respuesta.data) > 0
    except Exception:
        return False


def limpiar_tabla(tabla):
    try:
        supabase.table(tabla).delete().neq("id", 0).execute()
        print(f"  Tabla {tabla} limpiada antes de la ingesta.")
    except Exception as e:
        print(f"  [WARN] No se pudo limpiar la tabla {tabla}: {e}")


def cargar_hashes(tabla):
    hashes = set()
    inicio = 0
    while True:
        respuesta = (
            supabase.table(tabla)
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


def leer_archivo(ruta):
    sufijo = ruta.suffix.lower()

    if sufijo in {".txt", ".md"}:
        return ruta.read_text(encoding="utf-8", errors="replace")

    if sufijo == ".pdf":
        try:
            resultado = subprocess.run(
                ["pdftotext", "-layout", "-enc", "UTF-8", str(ruta), "-"],
                capture_output=True,
                text=True,
                timeout=120,
            )
            if resultado.returncode == 0:
                return resultado.stdout
        except Exception:
            pass

        import pdfplumber

        with pdfplumber.open(ruta) as pdf:
            return "\n".join((pagina.extract_text() or "") for pagina in pdf.pages)

    if sufijo == ".csv":
        import pandas as pd

        return pd.read_csv(ruta).to_csv(index=False)

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
        return resultado.stdout

    if sufijo in {".xlsx", ".xls", ".xlsm"}:
        import pandas as pd

        hojas = pd.read_excel(ruta, sheet_name=None)
        return "\n\n".join(
            f"### HOJA: {nombre}\n{tabla.to_csv(index=False)}"
            for nombre, tabla in hojas.items()
        )

    return ""


def listar_archivos(config):
    if "carpeta" in config:
        carpeta = Path(config["carpeta"])
        if not carpeta.is_dir():
            print(f"[ERROR] No existe la carpeta: {carpeta}")
            return []
        return sorted(
            ruta
            for ruta in carpeta.rglob("*")
            if ruta.is_file() and ruta.suffix.lower() in EXTENSIONES
        )

    ruta = DATA_DIR / config["archivo"]
    if not ruta.exists():
        print(f"[ERROR] No existe el archivo fusionado: {ruta}")
        return []
    return [ruta]


def insertar_lote(tabla, lote):
    try:
        supabase.table(tabla).insert(lote).execute()
        return len(lote), 0
    except Exception as error:
        print(f"    [WARN] Falló lote de {len(lote)}; reintentando uno a uno: {str(error)[:120]}")
        insertados = 0
        errores = 0
        for fila in lote:
            try:
                supabase.table(tabla).insert(fila).execute()
                insertados += 1
            except Exception as error_fila:
                errores += 1
                print(f"      [ERROR] {str(error_fila)[:120]}")
        return insertados, errores


def _hash_existe_directo(tabla, hash_origen):
    try:
        respuesta = (
            supabase.table(tabla)
            .select("id")
            .eq("hash_origen", hash_origen)
            .limit(1)
            .execute()
        )
        return len(respuesta.data) > 0
    except Exception:
        return False


def ingestar_tema(tema, limpiar=False, dry_run=False):
    if tema not in CONFIG_TEMAS:
        print(f"[ERROR] Tema desconocido: {tema}")
        return

    config = CONFIG_TEMAS[tema]
    tabla = config["tabla"]
    archivos = listar_archivos(config)
    if not archivos:
        return

    print(f"\n[{tema.upper()}] {len(archivos)} archivo(s) -> {tabla}")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=150,
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    if dry_run:
        total_chunks = 0
        total_unicos = 0
        hashes = set()
        for ruta in archivos:
            try:
                texto = leer_archivo(ruta)
            except Exception as error:
                print(f"  [ERROR] {ruta.name}: {str(error)[:120]}")
                continue
            chunks = splitter.split_text(texto)
            hashes_archivo = [generar_hash(chunk) for chunk in chunks]
            hashes.update(hashes_archivo)
            total_chunks += len(chunks)
            total_unicos += len(set(hashes_archivo))
            print(f"  {ruta.name}: {len(chunks)} fragmentos")
        print(
            f"  DRY-RUN: {total_chunks} fragmentos, {total_unicos} únicos por archivo, "
            f"{len(hashes)} únicos globales. No se escribió nada."
        )
        return

    if limpiar:
        limpiar_tabla(tabla)

    hashes_existentes = cargar_hashes(tabla)
    print(f"  Hashes existentes en {tabla}: {len(hashes_existentes)}")

    print("  Cargando modelo de embeddings...")
    modelo = SentenceTransformer("intfloat/multilingual-e5-small")

    total_insertados = 0
    total_duplicados = 0
    total_errores = 0
    total_chunks = 0
    archivos_ok = 0

    for ruta in archivos:
        print(f"  Procesando: {ruta.name}")
        try:
            texto = leer_archivo(ruta)
        except Exception as error:
            print(f"    [ERROR] No se pudo leer: {str(error)[:120]}")
            total_errores += 1
            continue

        if not texto.strip():
            print("    [WARN] Archivo vacío o sin texto extraíble.")
            continue

        chunks = splitter.split_text(texto)
        insertados_archivo = 0
        duplicados_archivo = 0
        errores_archivo = 0
        lote = []

        def volcar_lote():
            nonlocal insertados_archivo, errores_archivo
            if not lote:
                return
            insertados, errores = insertar_lote(tabla, lote)
            insertados_archivo += insertados
            errores_archivo += errores
            lote.clear()

        pendientes = []
        for chunk in chunks:
            if len(chunk.strip()) < 100:
                continue
            hash_txt = generar_hash(chunk)
            if hash_txt in hashes_existentes:
                duplicados_archivo += 1
                continue

            if _hash_existe_directo(tabla, hash_txt):
                duplicados_archivo += 1
                hashes_existentes.add(hash_txt)
                continue

            hashes_existentes.add(hash_txt)
            pendientes.append((hash_txt, chunk))

        for inicio in range(0, len(pendientes), 32):
            grupo = pendientes[inicio:inicio + 32]
            vectores = modelo.encode(
                [f"passage: {chunk}" for _, chunk in grupo],
                batch_size=32,
                show_progress_bar=False,
            )
            for (hash_txt, chunk), vector in zip(grupo, vectores):
                lote.append(
                    {
                        "contenido": chunk,
                        "metadata": {
                            "tema": tema,
                            "archivo": ruta.name,
                            "ruta": str(ruta),
                        },
                        "embedding": vector.tolist(),
                        "hash_origen": hash_txt,
                    }
                )
                if len(lote) >= LOTE_INSERCION:
                    volcar_lote()

        volcar_lote()

        total_chunks += len(chunks)
        total_insertados += insertados_archivo
        total_duplicados += duplicados_archivo
        total_errores += errores_archivo
        if insertados_archivo or duplicados_archivo or errores_archivo:
            archivos_ok += 1
        print(
            f"    {len(chunks)} fragmentos: {insertados_archivo} insertados, "
            f"{duplicados_archivo} duplicados, {errores_archivo} errores."
        )

    print(
        f"  RESUMEN {tema.upper()}: {total_chunks} fragmentos, "
        f"{total_insertados} insertados, {total_duplicados} duplicados, "
        f"{total_errores} errores, {archivos_ok} archivos con contenido."
    )


def main():
    parser = argparse.ArgumentParser(description="Ingesta de Coaches DepaFix")
    parser.add_argument("--tema", type=str, default="todos", help="Tema específico o 'todos'")
    parser.add_argument("--limpiar", action="store_true", help="Borrar tabla antes de insertar")
    parser.add_argument("--dry-run", action="store_true", help="Simular sin escribir en DB")
    args = parser.parse_args()

    if args.tema == "todos":
        temas_a_procesar = list(CONFIG_TEMAS.keys())
    elif args.tema in CONFIG_TEMAS:
        temas_a_procesar = [args.tema]
    else:
        print(f"[ERROR] Tema no válido: {args.tema}. Opciones: {list(CONFIG_TEMAS.keys())} o 'todos'")
        sys.exit(1)

    for t in temas_a_procesar:
        ingestar_tema(t, limpiar=args.limpiar, dry_run=args.dry_run)

    if not args.dry_run:
        print("\nProceso finalizado.")


if __name__ == "__main__":
    main()
