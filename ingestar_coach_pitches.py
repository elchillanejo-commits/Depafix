import os
from dotenv import load_dotenv
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS

load_dotenv()

# El "oro puro" que ya tenés
RUTA_FUENTE = "./pitch_inversionistas.md"
RUTA_DESTINO = "./coaches/pitches/faiss_index"

def main():
    if not os.path.exists(RUTA_FUENTE):
        print(f"❌ ERROR: No se encontró el archivo {RUTA_FUENTE}")
        return

    print(f"📖 Leyendo el pitch desde {RUTA_FUENTE}...")
    loader = TextLoader(RUTA_FUENTE, encoding="utf-8")
    docs = loader.load()

    print("✂️ Dividiendo en fragmentos...")
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    splits = text_splitter.split_documents(docs)

    print("🧠 Creando embeddings locales (Hugging Face) y guardando el Coach...")
    embeddings = HuggingFaceEmbeddings(model_name="intfloat/multilingual-e5-small")
    
    vectorstore = FAISS.from_documents(splits, embeddings)
    vectorstore.save_local(RUTA_DESTINO)
    
    print(f"✅ ¡Coach Pitches creado con éxito en {RUTA_DESTINO}!")

if __name__ == "__main__":
    main()
