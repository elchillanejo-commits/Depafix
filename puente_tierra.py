import os
from supabase import create_client
from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings

load_dotenv()
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_ROLE_KEY"))

print("Descargando datos de Supabase (tierra_knowledge)...")
res = supabase.table("tierra_knowledge").select("contenido", "metadata").execute()

if not res.data:
    print("❌ No hay datos en Supabase.")
    exit()

documentos = [Document(page_content=row["contenido"], metadata=row["metadata"]) for row in res.data]
print(f"✅ {len(documentos)} fragmentos descargados.")

print("Generando archivo local tierra.faiss...")
embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
vectorstore = FAISS.from_documents(documentos, embeddings)

os.makedirs("./data/tierra.faiss", exist_ok=True)
vectorstore.save_local("./data/tierra.faiss")
print("✅ Archivo tierra.faiss actualizado y listo para mente_360.py")
