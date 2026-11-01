import os
from dotenv import load_dotenv
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser

load_dotenv()

# Configuración del LLM (OpenCode Go)
llm = ChatOpenAI(
    model="deepseek-v4-pro",
    temperature=0.1,
    api_key=os.getenv("OPENCODE_API_KEY"),
    base_url="https://opencode.ai/inference/go/openai/v1",
    default_headers={
        "x-opencode-session": "depafix-auditoria",
        "User-Agent": "DepaFix-Auditor/1.0"
    }
)

# Leer los prompts de los profesores
with open("profesores/profesor_supervisor.md", "r") as f:
    PROMPT_SUPERVISOR = f.read()

with open("profesores/auditor_profesores.md", "r") as f:
    PROMPT_AUDITOR = f.read()

def limpiar_texto(texto):
    """Pasa el texto por el Profesor Supervisor y el Auditor."""
    print("🧑‍🏫 Profesor Supervisor clasificando...")
    prompt_sup = f"""
    {PROMPT_SUPERVISOR}
    
    Texto a evaluar:
    {texto}
    
    Devuelve SOLO el texto que consideres DATO DURO. Si es todo HUMO, devuelve una cadena vacía.
    """
    chain_sup = PromptTemplate(template=prompt_sup, input_variables=[]) | llm | StrOutputParser()
    texto_filtrado = chain_sup.invoke({})

    if not texto_filtrado.strip():
        print("🗑️ Todo era humo. Descartado.")
        return None

    print("🕵️ Auditor revisando duplicados...")
    prompt_aud = f"""
    {PROMPT_AUDITOR}
    
    Texto a auditar:
    {texto_filtrado}
    
    Si el texto es válido y no es duplicado, devuélvelo tal cual. Si es duplicado o tiene errores, devuelve una cadena vacía.
    """
    chain_aud = PromptTemplate(template=prompt_aud, input_variables=[]) | llm | StrOutputParser()
    texto_auditado = chain_aud.invoke({})

    if not texto_auditado.strip():
        print("🚫 Auditor rechazó el lote.")
        return None

    return texto_auditado

def ingestar_con_calidad(archivo_origen, ruta_destino):
    print(f"📖 Leyendo {archivo_origen}...")
    loader = TextLoader(archivo_origen, encoding="utf-8")
    docs = loader.load()

    print("✂️ Dividiendo en fragmentos...")
    # CORRECCIÓN: Pedazos más chicos para que el Profesor evalúe tema por tema
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=300, 
        chunk_overlap=50,
        separators=["\n\n", "\n", " ", ""]
    )
    splits = text_splitter.split_documents(docs)

    fragmentos_limpios = []
    for i, doc in enumerate(splits):
        print(f"\n--- Evaluando fragmento {i+1}/{len(splits)} ---")
        texto_limpio = limpiar_texto(doc.page_content)
        if texto_limpio:
            fragmentos_limpios.append(texto_limpio)

    if not fragmentos_limpios:
        print("❌ No quedó ningún fragmento válido.")
        return

    print(f"\n🧠 Generando embeddings para {len(fragmentos_limpios)} fragmentos...")
    embeddings = HuggingFaceEmbeddings(model_name="intfloat/multilingual-e5-small")
    vectorstore = FAISS.from_texts(fragmentos_limpios, embeddings)
    vectorstore.save_local(ruta_destino)
    print(f"✅ Coach creado en {ruta_destino} con {len(fragmentos_limpios)} fragmentos de calidad.")

if __name__ == "__main__":
    # ACÁ CAMBIAMOS A SHOPIFY
    ingestar_con_calidad("./conocimiento_shopify.txt", "./coaches/shopify/faiss_index")
