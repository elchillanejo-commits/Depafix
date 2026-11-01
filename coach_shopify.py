import os
from dotenv import load_dotenv
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser

load_dotenv()

llm = ChatOpenAI(
    model="deepseek-v4-pro",
    temperature=0.3,
    api_key=os.getenv("OPENCODE_API_KEY"),
    base_url="https://opencode.ai/inference/go/openai/v1",
    default_headers={
        "x-opencode-session": "depafix-coach-shopify",
        "User-Agent": "DepaFix-CoachShopify/1.0"
    }
)

RUTA_FAISS = "./coaches/shopify/faiss_index"
SYSTEM_PROMPT = "Eres un experto en Shopify y dropshipping. Responde de forma técnica y directa, con pasos concretos para configurar tiendas, importar productos y optimizar ventas."

def main():
    if not os.path.exists(RUTA_FAISS):
        print(f"❌ ERROR: No existe {RUTA_FAISS}. Ejecutá ingestar_con_calidad.py primero.")
        return
    print("🧠 Cargando Coach Shopify...")
    embeddings = HuggingFaceEmbeddings(model_name="intfloat/multilingual-e5-small")
    vectorstore = FAISS.load_local(RUTA_FAISS, embeddings, allow_dangerous_deserialization=True)
    print("✅ Coach Shopify listo.\n")
    while True:
        pregunta = input("\n💬 Pregunta (o 'salir'): ")
        if pregunta.lower() in ['salir', 'exit', 'quit']:
            break
        if not pregunta.strip():
            continue
        print("🔍 Buscando en el cerebro...")
        resultados = vectorstore.similarity_search(pregunta, k=3)
        contexto = "\n".join([doc.page_content for doc in resultados])
        print("🤔 Redactando respuesta...")
        prompt_template = f"""
        {SYSTEM_PROMPT}
        Contexto de referencia:
        {contexto}
        Pregunta: {pregunta}
        Respuesta:
        """
        chain = PromptTemplate(template=prompt_template, input_variables=["pregunta"]) | llm | StrOutputParser()
        respuesta = chain.invoke({"pregunta": pregunta})
        print("\n" + "="*50)
        print(respuesta)
        print("="*50)

if __name__ == "__main__":
    main()
