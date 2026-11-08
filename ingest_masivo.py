import os
import sys
import subprocess
from pathlib import Path
from supabase import create_client, Client

# Configuración de Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("Error: Faltan variables de entorno SUPABASE_URL o SUPABASE_SERVICE_ROLE_KEY")
    sys.exit(1)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
TABLA_DESTINO = "knowledge_chunks_v2" # <-- CORREGIDO AQUÍ

def chequear_duplicado(nombre_archivo: str) -> bool:
    res = supabase.table(TABLA_DESTINO).select("id").eq("source_file", nombre_archivo).limit(1).execute()
    return len(res.data) > 0

def contar_chunks(nombre_archivo: str) -> int:
    res = supabase.table(TABLA_DESTINO).select("id", count="exact").eq("source_file", nombre_archivo).execute()
    return res.count if res.count is not None else len(res.data)

def main():
    directorio_base = Path("data/transcripciones")
    
    if not directorio_base.exists():
        print(f"Error: El directorio {directorio_base} no existe.")
        sys.exit(1)

    resumen = {"procesados": 0, "omitidos": 0, "errores": 0, "chunks_insertados": 0, "archivos_con_error": []}
    print(f"Iniciando escaneo en: {directorio_base}...\n")

    for subcarpeta in directorio_base.iterdir():
        if not subcarpeta.is_dir(): continue
            
        domain = subcarpeta.name
        print(f"Explorando domain: [{domain}]")
        
        for archivo in subcarpeta.glob("*.*"):
            if not archivo.is_file(): continue
            nombre_archivo = archivo.name
            
            try:
                if chequear_duplicado(nombre_archivo):
                    print(f"  [OMITIDO] '{nombre_archivo}' ya existe en BD.")
                    resumen["omitidos"] += 1
                    continue
            except Exception as e:
                print(f"  [ERROR BD] Falló verificación de '{nombre_archivo}': {e}")
                resumen["errores"] += 1
                resumen["archivos_con_error"].append(nombre_archivo)
                continue

            print(f"  [PROCESANDO] '{nombre_archivo}' -> Domain: {domain}...")
            try:
                # Ajusta si tu script requiere otra ruta (ej. "ingest/knowledge/ingest_transcripts.py")
                subprocess.run(
                    [sys.executable, "ingest_transcripts.py", "--file", str(archivo), "--domain", domain],
                    capture_output=True, text=True, check=True
                )
                chunks_creados = contar_chunks(nombre_archivo)
                resumen["chunks_insertados"] += chunks_creados
                resumen["procesados"] += 1
                print(f"    -> OK: {chunks_creados} chunks registrados.")
            except subprocess.CalledProcessError as e:
                print(f"  [ERROR INGESTA] Falló '{nombre_archivo}'.")
                print(f"    Detalle stderr: {e.stderr.strip()}")
                resumen["errores"] += 1
                resumen["archivos_con_error"].append(nombre_archivo)

    print("\n" + "="*50)
    print(" RESUMEN DE INGESTA MASIVA")
    print("="*50)
    print(f" Archivos procesados con éxito : {resumen['procesados']}")
    print(f" Total de chunks insertados    : {resumen['chunks_insertados']}")
    print(f" Archivos omitidos (duplicados): {resumen['omitidos']}")
    print(f" Errores de procesamiento      : {resumen['errores']}")
    if resumen["errores"] > 0:
        print("\n Archivos con error:")
        for err_file in resumen["archivos_con_error"]:
            print(f"  - {err_file}")
    print("="*50)

if __name__ == "__main__":
    main()
