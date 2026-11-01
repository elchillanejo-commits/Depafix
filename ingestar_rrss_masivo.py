import os
from dotenv import load_dotenv
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser

load_dotenv()

llm = ChatOpenAI(
    model="deepseek-v4-pro",
    temperature=0.1,
    api_key=os.getenv("OPENCODE_API_KEY"),
    base_url="https://opencode.ai/inference/go/openai/v1",
    default_headers={
        "x-opencode-session": "depafix-rrss",
        "User-Agent": "DepaFix-RRSS/1.0"
    }
)

with open("profesores/profesor_supervisor.md", "r") as f:
    PROMPT_SUPERVISOR = f.read()
with open("profesores/auditor_profesores.md", "r") as f:
    PROMPT_AUDITOR = f.read()
with open("profesores/regulador_profesores.md", "r") as f:
    PROMPT_REGULADOR = f.read()

def consultar_regulador(texto_original, texto_auditor):
    prompt_reg = f"""{PROMPT_REGULADOR}

Texto original del fragmento:
{texto_original}

Dato que el Auditor rechazó:
{texto_auditor}

Segunda opinión:
- Si el rechazo fue un falso positivo y el dato es técnico/verificable, devuelve SOLO el dato duro (conserva cifras, pasos y detalles técnicos).
- Si es humo, duplicado, opinión o relleno, devuelve exactamente: RECHAZADO
No agregues explicaciones."""
    chain_reg = PromptTemplate(template=prompt_reg, input_variables=[]) | llm | StrOutputParser()
    veredicto = chain_reg.invoke({}).strip()
    if not veredicto or veredicto.upper().startswith("RECHAZADO"):
        return None
    return veredicto

def limpiar_texto(texto):
    # Profesor
    prompt_sup = f"{PROMPT_SUPERVISOR}\n\nTexto a evaluar:\n{texto}\n\nDevuelve SOLO el DATO DURO. Si es HUMO, devuelve vacío."
    chain_sup = PromptTemplate(template=prompt_sup, input_variables=[]) | llm | StrOutputParser()
    texto_filtrado = chain_sup.invoke({})
    if not texto_filtrado.strip():
        return None
    # Auditor
    prompt_aud = f"{PROMPT_AUDITOR}\n\nTexto a auditar:\n{texto_filtrado}\n\nSi es válido, devuélvelo. Si es duplicado/error, vacío."
    chain_aud = PromptTemplate(template=prompt_aud, input_variables=[]) | llm | StrOutputParser()
    texto_auditado = chain_aud.invoke({}).strip()
    if texto_auditado:
        return texto_auditado
    # Regulador: segunda opinión antes de descartar
    print("⚖️ Auditor rechazó el lote; consultando al Regulador...")
    aprobado = consultar_regulador(texto, texto_filtrado)
    if aprobado:
        print("⚖️ Regulador aprobó: era un falso positivo.")
        return aprobado
    print("⚖️ Regulador confirmó el rechazo.")
    return None

def ingestar_carpeta(ruta_origen, ruta_destino):
    print(f"📂 Leyendo carpeta: {ruta_origen}")
    loader = DirectoryLoader(ruta_origen, glob="*.txt", loader_cls=TextLoader, loader_kwargs={'encoding': 'utf-8'})
    docs = loader.load()
    
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=100, separators=["\n\n", "\n", " ", ""])
    splits = text_splitter.split_documents(docs)
    
    fragmentos_limpios = []
    for i, doc in enumerate(splits):
        print(f"\n--- Evaluando fragmento {i+1}/{len(splits)} (fuente: {doc.metadata.get('source', '?')}) ---")
        limpio = limpiar_texto(doc.page_content)
        if limpio:
            fragmentos_limpios.append(limpio)
            print("✅ Aprobado.")
        else:
            print("🗑️ Rechazado (humo o duplicado).")

    if not fragmentos_limpios:
        print("❌ No quedó nada válido.")
        return

    print(f"\n🧠 Generando embeddings para {len(fragmentos_limpios)} fragmentos...")
    embeddings = HuggingFaceEmbeddings(model_name="intfloat/multilingual-e5-small")
    vectorstore = FAISS.from_texts(fragmentos_limpios, embeddings)
    vectorstore.save_local(ruta_destino)
    print(f"✅ Coach RRSS creado en {ruta_destino} con {len(fragmentos_limpios)} fragmentos de calidad.")

if __name__ == "__main__":
    ingestar_carpeta("/home/ibar/Documentos/Conocimiento/RRSS_IA", "./coaches/rrss/faiss_index")
