import os
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings

# --- CONFIGURACIÓN ---
CARPETA_RAIZ = "/home/ibar/Documentos/Conocimiento"
CARPETA_SALIDA = "./data"

# Mapeo de carpetas a los 5 elementos (Puedes ajustar "Filosofia" a Metal)
MAPA_ELEMENTOS = {
    "Trade": "tierra",
    "Dropshipping": "agua",
    "Dropshiphing": "agua",
    "Agua_Dropshipping": "agua",
    "Ventas": "aire",
    "IA": "fuego",
    "Filosofia": "metal"
}

def ingestar():
    print(f"📂 Iniciando escaneo de: {CARPETA_RAIZ}")
    
    # Diccionario para agrupar documentos por elemento
    documentos_por_elemento = {k: [] for k in MAPA_ELEMENTOS.values()}
    documentos_por_elemento["general"] = [] # Por si hay archivos sueltos

    # 1. Cargar y clasificar documentos
    for root, dirs, files in os.walk(CARPETA_RAIZ):
        nombre_carpeta = os.path.basename(root)
        elemento = MAPA_ELEMENTOS.get(nombre_carpeta, "general")

        for archivo in files:
            if archivo.endswith(".txt"):
                ruta_completa = os.path.join(root, archivo)
                try:
                    loader = TextLoader(ruta_completa, encoding="utf-8")
                    docs = loader.load()
                    # Inyectar metadatos
                    for doc in docs:
                        doc.metadata["elemento"] = elemento
                        doc.metadata["fuente"] = archivo
                    
                    documentos_por_elemento[elemento].extend(docs)
                except Exception as e:
                    print(f"⚠️ Error leyendo {archivo}: {e}")

    # 2. Configuración de Embeddings y Splitter
    print("🧠 Configurando modelo de embeddings...")
    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    
    os.makedirs(CARPETA_SALIDA, exist_ok=True)

    # 3. Procesar y guardar cada elemento en su propio FAISS
    print("\n⚙️ Generando índices vectoriales separados...")
    for elemento, documentos in documentos_por_elemento.items():
        if not documentos:
            print(f"⚠️ Índice '{elemento}' omitido: no hay documentos.")
            continue

        chunks = text_splitter.split_documents(documentos)
        if not chunks:
            print(f"⚠️ Índice '{elemento}' omitido: no hay texto para indexar.")
            continue

        archivo_faiss = os.path.join(CARPETA_SALIDA, f"{elemento}.faiss")
        print(f"⏳ Vectorizando '{elemento}' ({len(chunks)} fragmentos)...")
        
        vectorstore = FAISS.from_documents(chunks, embeddings)
        vectorstore.save_local(archivo_faiss)
        
        print(f"✅ Índice '{elemento}' guardado en {archivo_faiss}")

if __name__ == "__main__":
    ingestar()
