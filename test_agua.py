import os
from dotenv import load_dotenv
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings

# Cargar variables de entorno (.env)
load_dotenv()

INDEX_DIR = "./data/agua.faiss"
QUERY = "¿Cómo elegir un producto ganador para dropshipping?"

if not os.path.exists(INDEX_DIR):
    print(f"❌ No se encontró {INDEX_DIR}")
else:
    print(f"🔍 Cargando cerebro desde {INDEX_DIR}...")
    embeddings = OpenAIEmbeddings()
    vectorstore = FAISS.load_local(INDEX_DIR, embeddings, allow_dangerous_deserialization=True)

    print(f"🤔 Preguntando: '{QUERY}'\n")
    results = vectorstore.similarity_search_with_score(QUERY, k=3)

    for i, (doc, score) in enumerate(results, 1):
        print(f"--- Resultado {i} (Score: {score:.4f}) ---")
        texto_limpio = doc.page_content.replace('\n', ' ')
        print(f"{texto_limpio[:600]}...\n")
