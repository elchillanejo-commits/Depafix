import os
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS

# FORZAMOS LA RUTA CORRECTA (con H)
CARPETA_ORIGEN = "/home/ibar/Documentos/Conocimiento/Dropshiphing"
CARPETA_DESTINO = "./data/agua.faiss"

def main():
    archivos = [f for f in os.listdir(CARPETA_ORIGEN) if f.endswith('.txt')]
    print(f"📂 Carpeta elegida: {CARPETA_ORIGEN}")
    print(f"📂 Archivos .txt encontrados: {len(archivos)}")

    loader = DirectoryLoader(
        CARPETA_ORIGEN, 
        glob="*.txt", 
        loader_cls=TextLoader,
        loader_kwargs={'encoding': 'utf-8'}
    )
    docs = loader.load()
    print(f"📄 Documentos cargados: {len(docs)}")

    print("✂️ Dividiendo en fragmentos...")
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    splits = text_splitter.split_documents(docs)

    print("🧠 Creando embeddings (Gratis, local) y guardando cerebro Agua...")
    # Usamos el mismo modelo que los otros cerebros para evitar errores de dimensiones
    embeddings = HuggingFaceEmbeddings(model_name="intfloat/multilingual-e5-small")
    
    vectorstore = FAISS.from_documents(splits, embeddings)
    vectorstore.save_local(CARPETA_DESTINO)
    
    print(f"✅ ¡Cerebro Agua generado con éxito en {CARPETA_DESTINO}!")

if __name__ == "__main__":
    main()
