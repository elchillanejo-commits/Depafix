#!/usr/bin/env python3
"""
ingestar_tierra.py — Ingesta SERVIU con clasificación inteligente.
Usa el Profesor de Tierra para separar NORMATIVA (metal) de CALCULO (tierra).
"""
import os
import sys
import glob
import json
import hashlib
from pathlib import Path
from dotenv import load_dotenv
from supabase import create_client
from sentence_transformers import SentenceTransformer
import pdfplumber
import pandas as pd
from openai import OpenAI

# === CONFIGURACIÓN ===
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not all([SUPABASE_URL, SUPABASE_KEY, OPENAI_API_KEY]):
    print("❌ Faltan credenciales en el .env")
    sys.exit(1)

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
client = OpenAI(api_key=OPENAI_API_KEY)

CARPETA = "/home/ibar/Documentos/Conocimiento/Tierra_Construccion/"
PROMPT_FILE = Path("profesores/tierra.md")

# Leer el System Prompt
if not PROMPT_FILE.exists():
    print("❌ No existe profesores/tierra.md")
    sys.exit(1)
SYSTEM_PROMPT = PROMPT_FILE.read_text(encoding="utf-8")

# Modelo de embeddings
print("🧠 Cargando modelo de embeddings...")
modelo = SentenceTransformer("intfloat/multilingual-e5-small")

# === FUNCIONES AUXILIARES ===
def generar_hash(texto):
    return hashlib.sha256(texto.encode('utf-8')).hexdigest()

def clasificar_lote(fragmentos):
    """Envía un lote de fragmentos al Profesor de Tierra."""
    texto_lote = "\n\n---\n\n".join([f"FRAGMENTO {i+1}:\n{f[:1500]}" for i, f in enumerate(fragmentos)])
    prompt = f"Clasifica los siguientes {len(fragmentos)} fragmentos. Devuelve SOLO un JSON con un array 'resultados', donde cada elemento tenga la clave 'clasificacion'.\n\n{texto_lote}"
    
    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.0
        )
        return json.loads(resp.choices[0].message.content).get("resultados", [])
    except Exception as e:
        print(f"  ⚠️ Error al clasificar lote: {e}")
        return [{"clasificacion": "BASURA"} for _ in fragmentos]

def insertar_fragmento(texto, tabla, tema):
    """Genera embedding e inserta en Supabase con idempotencia."""
    hash_txt = generar_hash(texto)
    
    try:
        existe = supabase.table(tabla).select("id").eq("hash_origen", hash_txt).execute()
        if existe.data:
            return "duplicado"
        
        vector = modelo.encode(f"passage: {texto}").tolist()
        supabase.table(tabla).insert({
            "contenido": texto,
            "metadata": {"tema": tema, "origen": "serviu"},
            "embedding": vector,
            "hash_origen": hash_txt
        }).execute()
        return "insertado"
    except Exception as e:
        print(f"    ❌ Error insertando: {e}")
        return "error"

# === PROCESAMIENTO DE ARCHIVOS ===
def extraer_texto(archivo):
    try:
        if archivo.endswith('.pdf'):
            texto = ""
            with pdfplumber.open(archivo) as pdf:
                for pagina in pdf.pages:
                    texto += (pagina.extract_text() or "") + "\n"
            return texto
        elif archivo.endswith(('.txt', '.md')):
            return Path(archivo).read_text(encoding="utf-8", errors="ignore")
        elif archivo.endswith(('.csv', '.xlsx', '.xls')):
            df = pd.read_csv(archivo) if archivo.endswith('.csv') else pd.read_excel(archivo)
            return df.to_csv(index=False)
    except Exception as e:
        print(f"  ⚠️ Error leyendo {archivo}: {e}")
        return ""
    return ""

# === MAIN ===
def main():
    archivos = glob.glob(CARPETA + "*.pdf") + glob.glob(CARPETA + "*.xlsx") + \
               glob.glob(CARPETA + "*.xls") + glob.glob(CARPETA + "*.txt") + \
               glob.glob(CARPETA + "*.md")
    
    if not archivos:
        print("⚠️ No hay archivos en la carpeta.")
        return
    
    print(f"📁 Encontrados {len(archivos)} archivos.")
    
    stats = {"metal": 0, "tierra": 0, "basura": 0, "duplicados": 0, "errores": 0}
    
    for archivo in archivos:
        nombre = os.path.basename(archivo)
        print(f"\n📄 Procesando: {nombre}")
        
        texto = extraer_texto(archivo)
        if not texto.strip():
            print(f"  ⚠️ Archivo vacío o sin texto: {nombre}")
            stats["basura"] += 1
            continue
        
        # Chunking
        chunks = [texto[i:i+1000] for i in range(0, len(texto), 1000) if len(texto[i:i+1000].strip()) > 100]
        print(f"  → {len(chunks)} fragmentos generados")
        
        # Clasificar en lotes de 5
        for i in range(0, len(chunks), 5):
            lote = chunks[i:i+5]
            clasificaciones = clasificar_lote(lote)
            
            for idx, chunk in enumerate(lote):
                if idx >= len(clasificaciones):
                    break
                cat = clasificaciones[idx].get("clasificacion", "BASURA")
                
                if cat == "NORMATIVA":
                    resultado = insertar_fragmento(chunk, "coach_metal", "metal")
                    stats["metal"] += 1
                elif cat == "CALCULO":
                    resultado = insertar_fragmento(chunk, "coach_tierra", "tierra")
                    stats["tierra"] += 1
                else:
                    resultado = "descartado"
                    stats["basura"] += 1
                
                if resultado == "duplicado":
                    stats["duplicados"] += 1
                elif resultado == "error":
                    stats["errores"] += 1
    
    print("\n" + "=" * 50)
    print("📊 RESUMEN DE INGESTA")
    print("=" * 50)
    print(f"  ✅ Insertados en METAL (Normativa):  {stats['metal']}")
    print(f"  ✅ Insertados en TIERRA (Cálculos):  {stats['tierra']}")
    print(f"  🗑️  Descartados como BASURA:          {stats['basura']}")
    print(f"  🔄 Duplicados omitidos:              {stats['duplicados']}")
    print(f"  ❌ Errores:                          {stats['errores']}")
    print("=" * 50)

if __name__ == "__main__":
    main()
