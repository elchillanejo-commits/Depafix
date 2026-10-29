import os
import glob
import pdfplumber
import pandas as pd
from supabase import create_client
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv

load_dotenv()
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
supabase = create_client(url, key)

print("Cargando modelo de embeddings...")
modelo = SentenceTransformer("intfloat/multilingual-e5-small")

carpeta = "/home/ibar/Documentos/Conocimiento/Metal_Procurador/"
archivos_pdf = glob.glob(carpeta + "*.pdf")
archivos_excel = glob.glob(carpeta + "*.xlsx") + glob.glob(carpeta + "*.xls") + glob.glob(carpeta + "*.csv")
archivos_txt = glob.glob(carpeta + "*.txt")

archivos = archivos_pdf + archivos_excel + archivos_txt

if not archivos:
    print("⚠️ No se encontraron archivos.")
else:
    print(f"📁 Encontrados {len(archivos_pdf)} PDFs, {len(archivos_excel)} Excels y {len(archivos_txt)} TXTs.")
    
    exitos = 0
    errores = 0
    
    for archivo in archivos:
        nombre = os.path.basename(archivo)
        print(f"Procesando: {nombre}")
        texto_completo = ""
        
        try:
            if archivo.endswith('.pdf'):
                with pdfplumber.open(archivo) as pdf:
                    for pagina in pdf.pages:
                        texto_completo += (pagina.extract_text() or "") + "\n"
            elif archivo.endswith('.txt'):
                with open(archivo, "r", encoding="utf-8") as f:
                    texto_completo = f.read()
            else:
                if archivo.endswith('.csv'):
                    df = pd.read_csv(archivo)
                else:
                    df = pd.read_excel(archivo)
                texto_completo = df.to_csv(index=False)
                
            if not texto_completo.strip():
                print(f"  ⚠️ Archivo vacío: {nombre}")
                continue
            
            chunk_size = 1000
            chunks = [texto_completo[i:i+chunk_size] for i in range(0, len(texto_completo), chunk_size)]
            print(f"  -> Generando {len(chunks)} fragmentos...")
            
            for chunk in chunks:
                if len(chunk.strip()) < 100: continue
                
                vector = modelo.encode(f"passage: {chunk}").tolist()
                
                data = {
                    "contenido": chunk,
                    "metadata": {"elemento": "metal", "fuente": nombre},
                    "embedding": vector
                }
                supabase.table("metal_knowledge").insert(data).execute()
            
            exitos += 1
            
        except Exception as e:
            print(f"  ❌ Error en {nombre}: {str(e)[:100]}")
            errores += 1
            
    print(f"\n✅ INGESTA FINALIZADA: {exitos} archivos subidos, {errores} fallidos.")
