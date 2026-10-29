import os
from dotenv import load_dotenv
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser

load_dotenv()

# ==========================================
# CONFIGURACIÓN DEL LLM (KIMI / MOONSHOT)
# ==========================================
llm = ChatOpenAI(
    model="kimi-k3.1-pro",  # <--- Modelo actualizado a la versión vigente
    temperature=0,
    api_key=os.getenv("MOONSHOT_API_KEY"),
    base_url="https://api.moonshot.ai/v1"
)

CEREBROS = {
    "Tierra": "./data/tierra.faiss",
    "Metal": "./data/metal.faiss",
    "Agua": "./data/agua.faiss",
    "Aire": "./data/aire.faiss",
    "Fuego": "./data/fuego.faiss"
}

def cargar_cerebros():
    print("📥 Cargando modelo de embeddings local (Hugging Face)...")
    embeddings = HuggingFaceEmbeddings(model_name="intfloat/multilingual-e5-small")
    cerebros_cargados = {}
    
    print("🧠 Despertando la Mente 360...")
    for nombre, ruta in CEREBROS.items():
        if os.path.exists(ruta):
            try:
                vs = FAISS.load_local(ruta, embeddings, allow_dangerous_deserialization=True)
                cerebros_cargados[nombre] = vs
                print(f"  ✅ {nombre} conectado.")
            except Exception as e:
                print(f"  ⚠️ Error al cargar {nombre}: {e}")
        else:
            print(f"  ❌ {nombre} no encontrado en {ruta} (ignorado).")
    return cerebros_cargados

def enrutar_pregunta(pregunta):
    print("🧭 Enrutando la pregunta a los cerebros correctos...")
    prompt = """
    Eres el enrutador de la Mente 360. Tienes 5 áreas: Tierra (Construcción), Metal (Legal), Agua (Dropshipping), Aire (Marketing), Fuego (Tecnología).
    Dada la pregunta del usuario, responde SOLO con una lista separada por comas de las áreas relevantes (ej: "Agua, Metal"). No agregues texto extra.
    Si la pregunta es muy general o no sabes, responde "Todas".
    
    Pregunta: {pregunta}
    """
    chain = PromptTemplate(template=prompt, input_variables=["pregunta"]) | llm | StrOutputParser()
    resultado = chain.invoke({"pregunta": pregunta}).strip()
    
    if "Todas" in resultado:
        return list(CEREBROS.keys())
    
    areas = [c.strip() for c in resultado.split(",") if c.strip() in CEREBROS]
    return areas if areas else list(CEREBROS.keys())

def consultar_mente_360(pregunta, cerebros):
    if not cerebros:
        return "No hay cerebros cargados para responder."

    areas_a_consultar = enrutar_pregunta(pregunta)
    print(f"🎯 Áreas seleccionadas: {', '.join(areas_a_consultar)}\n")

    contexto_combinado = ""
    print(f"🔍 Buscando información...")
    
    for nombre in areas_a_consultar:
        if nombre in cerebros:
            vs = cerebros[nombre]
            resultados = vs.similarity_search(pregunta, k=3)
            for doc in resultados:
                contexto_combinado += f"\n[Fuente: {nombre}]\n{doc.page_content}\n"
            print(f"  🔎 Búsqueda exitosa en {nombre}")

    print("🤔 Sintetizando respuesta con Kimi...")
    
    prompt_template = """
    Eres la "Mente 360" del sistema DepaFix. Responde de forma clara y accionable.
    Usa el siguiente contexto recuperado. Si el contexto no tiene la respuesta, di que no lo sabes.
    
    Contexto:
    {contexto}
    
    Pregunta: {pregunta}
    
    Respuesta:
    """
    
    chain = PromptTemplate(template=prompt_template, input_variables=["contexto", "pregunta"]) | llm | StrOutputParser()
    return chain.invoke({"contexto": contexto_combinado, "pregunta": pregunta})

if __name__ == "__main__":
    if not os.getenv("MOONSHOT_API_KEY"):
        print("❌ ERROR: Falta la MOONSHOT_API_KEY en el archivo .env")
        exit(1)

    mis_cerebros = cargar_cerebros()
    print(f"✅ {len(mis_cerebros)} cerebros cargados.\n")
    
    while True:
        pregunta = input("\n💬 Pregunta para la Mente 360 (o escribe 'salir'): ")
        if pregunta.lower() in ['salir', 'exit', 'quit']:
            break
        if not pregunta.strip():
            continue
            
        respuesta = consultar_mente_360(pregunta, mis_cerebros)
        print("\n" + "="*50)
        print(respuesta)
        print("="*50)
