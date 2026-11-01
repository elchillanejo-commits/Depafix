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
        "x-opencode-session": "depafix-coach-rrss",
        "User-Agent": "DepaFix-CoachRRSS/1.0"
    }
)

RUTA_FAISS = "./coaches/rrss/faiss_index"
# Tabla de Supabase donde se guarda el conocimiento de este coach (usada en la ingesta, no en el chat)
TABLA_SUPABASE = "coach_rrss"
SYSTEM_PROMPT = "Eres el Coach de RRSS de DepaFix. Eres experto en Meta Ads, copywriting, Reels y métricas de conversión. Tu misión es ayudar a dueños de PYMES a convertir seguidores en clientes con tácticas concretas."

def main():
    if not os.path.exists(RUTA_FAISS):
        print(f"❌ ERROR: No existe {RUTA_FAISS}. Ejecutá la ingesta del coach RRSS primero.")
        return
    print("🧠 Cargando Coach RRSS...")
    embeddings = HuggingFaceEmbeddings(model_name="intfloat/multilingual-e5-small")
    vectorstore = FAISS.load_local(RUTA_FAISS, embeddings, allow_dangerous_deserialization=True)
    print("✅ Coach RRSS listo.\n")
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
