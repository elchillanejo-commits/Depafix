import os
from dotenv import load_dotenv
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser

load_dotenv()

# 1. Ruta del índice FAISS local
RUTA_FAISS = "./coaches/pitches/faiss_index/"

# 2. Configuración del LLM (OpenCode Go - deepseek-v4-pro)
llm = ChatOpenAI(
    model="deepseek-v4-pro",
    api_key=os.getenv("OPENCODE_API_KEY"),
    base_url="https://opencode.ai/inference/go/openai/v1",
    default_headers={
        "x-opencode-session": "depafix-coach-pitches",
        "User-Agent": "depafix-coach/1.0"
    }
)

# 3. System Prompt experto en pitches de venta B2B
SYSTEM_PROMPT = """Eres el "Coach de Pitches" de DepaFix, experto en ventas consultivas B2B, prospección comercial y cierres de alto impacto.
Tu misión es redactar y optimizar mensajes de WhatsApp, emails y guiones de venta B2B cortos, directos, con tono par-a-par (de dueño a dueño) y enfocados en concretar una reunión.
Usa el contexto recuperado de tu índice local para inspirarte y dar respuestas precisas."""

PROMPT_TEMPLATE = """{system_prompt}

Contexto de referencia:
{contexto}

Pregunta del usuario: {pregunta}

Respuesta:"""


def main():
    if not os.getenv("OPENCODE_API_KEY"):
        print("❌ ERROR: Falta OPENCODE_API_KEY en el archivo .env")
        return

    if not os.path.exists(RUTA_FAISS):
        print(f"❌ ERROR: No existe el índice en {RUTA_FAISS}. Ejecutá 'python ingestar_coach_pitches.py' primero.")
        return

    print("📥 Cargando modelo de embeddings local...")
    embeddings = HuggingFaceEmbeddings(model_name="intfloat/multilingual-e5-small")
    vectorstore = FAISS.load_local(RUTA_FAISS, embeddings, allow_dangerous_deserialization=True)

    chain = (
        PromptTemplate(
            template=PROMPT_TEMPLATE,
            input_variables=["system_prompt", "contexto", "pregunta"],
        )
        | llm
        | StrOutputParser()
    )

    print("✅ Coach de Pitches (100% Local) listo. Escribe 'salir' para terminar.\n")

    # 4. Chat por consola
    while True:
        try:
            pregunta = input("\n💬 Tú: ")
        except EOFError:
            break
        if pregunta.lower() in ["salir", "exit", "quit"]:
            break
        if not pregunta.strip():
            continue

        print("🔍 Buscando en el índice FAISS local...")
        docs = vectorstore.similarity_search(pregunta, k=3)
        contexto = "\n\n".join([d.page_content for d in docs])

        print("🤔 Redactando pitch...")
        respuesta = chain.invoke(
            {
                "system_prompt": SYSTEM_PROMPT,
                "contexto": contexto,
                "pregunta": pregunta,
            }
        )

        print("\n" + "=" * 50)
        print(respuesta)
        print("=" * 50)


if __name__ == "__main__":
    main()
