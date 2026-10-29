import os
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings

CARPETA_DATA = "./data"

# Diccionario para saber a qué cerebro preguntar
MAPEO_PREGUNTA = {
    "venta": "aire", "vender": "aire", "persuasion": "aire", "cliente": "aire", "speech": "aire",
    "trade": "tierra", "mercado": "tierra", "acciones": "tierra", "cripto": "tierra",
    "ia": "fuego", "mcp": "fuego", "agente": "fuego", "codigo": "fuego", "opencode": "fuego",
    "filosofia": "metal", "estoicismo": "metal", "eneagrama": "metal", "marco aurelio": "metal", "sun tzu": "metal"
}

def buscar():
    print("\n" + "="*50)
    print("🧠 BUSCADOR INTELIGENTE (Mente 360)")
    print("="*50)
    pregunta = input("🔎 ¿Qué quieres buscar? (ej: 'cómo vender', 'marco aurelio', 'mcp'): ")
    
    # 1. Detectar el cerebro según palabras clave
    elemento = "general" # Por defecto busca en general
    for clave, valor in MAPEO_PREGUNTA.items():
        if clave in pregunta.lower():
            elemento = valor
            break

    archivo_faiss = os.path.join(CARPETA_DATA, f"{elemento}.faiss")
    
    if not os.path.exists(archivo_faiss):
        print(f"❌ No existe el cerebro '{elemento}'. Revisa la carpeta data/.")
        return

    print(f"\n🧠 Conectando al cerebro '{elemento.upper()}'...")
    
    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    vectorstore = FAISS.load_local(archivo_faiss, embeddings, allow_dangerous_deserialization=True)
    
    resultados = vectorstore.similarity_search(pregunta, k=3)
    
    print("\n" + "="*50)
    print(f"✅ CONTEXTO ENCONTRADO EN '{elemento.upper()}' (Copia esto y pégalo en Kimi):")
    print("="*50)
    for i, doc in enumerate(resultados):
        print(f"\n--- Fragmento {i+1} (Fuente: {doc.metadata.get('fuente', '?')}) ---")
        print(doc.page_content)
    print("\n" + "="*50)

if __name__ == "__main__":
    buscar()
