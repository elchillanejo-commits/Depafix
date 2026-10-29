import os
import requests
from bs4 import BeautifulSoup
import trafilatura
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import StrOutputParser
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from dotenv import load_dotenv

load_dotenv()

def extraer_texto_web(url):
    print(f"\n🌐 Analizando: {url}")
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
        texto_limpio = trafilatura.extract(response.text)
        if not texto_limpio:
            soup = BeautifulSoup(response.text, 'html.parser')
            texto_limpio = soup.get_text(separator=' ', strip=True)
        
        # Filtro de Seguridad
        frases_peligrosas = ["ignora las instrucciones", "ignore previous instructions", "system prompt", "olvida todo"]
        for frase in frases_peligrosas:
            if frase.lower() in texto_limpio.lower():
                print(f"   🚨 ¡ADVERTENCIA! Detectada inyección de prompt: '{frase}'. Filtrado.")
                texto_limpio = texto_limpio.lower().replace(frase.lower(), "[TEXTO ELIMINADO]")
                
        return texto_limpio
    except Exception as e:
        print(f"   ❌ Error al acceder a la web: {e}")
        return None

def analizar_conocimiento(texto, url):
    print("🤔 Analizando el conocimiento con el Oráculo...")
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.1)
    
    prompt = """
    Eres un Ingeniero de Datos Senior. Acabas de extraer el texto de la siguiente web: {url}.
    
    Realiza un "Análisis Duro y Preciso":
    1. Clasifica la web (Tecnológica, Media, Arcaica, Educativa, etc.).
    2. Resume los 3 puntos más importantes de conocimiento que aporta esta web.
    3. Responde a la pregunta crítica: ¿Qué conocimientos NOS FALTAN sobre este tema para dominarlo por completo?
    
    Texto extraído:
    {texto}
    """
    
    chain = PromptTemplate(template=prompt, input_variables=["url", "texto"]) | llm | StrOutputParser()
    return chain.invoke({"url": url, "texto": texto[:15000]})

def guardar_en_cerebro(texto, url, cerebro_elegido):
    print(f"💾 Guardando conocimiento en el cerebro: {cerebro_elegido}...")
    ruta_faiss = f"./data/{cerebro_elegido}.faiss"
    
    if not os.path.exists(ruta_faiss):
        print(f"❌ No existe el cerebro {cerebro_elegido}.")
        return

    embeddings = HuggingFaceEmbeddings(model_name="intfloat/multilingual-e5-small")
    vectorstore = FAISS.load_local(ruta_faiss, embeddings, allow_dangerous_deserialization=True)
    
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    splits = text_splitter.create_documents([texto], metadatas=[{"source": url}])
    
    vectorstore.add_documents(splits)
    vectorstore.save_local(ruta_faiss)
    print(f"✅ ¡Conocimiento inyectado con éxito en {cerebro_elegido}!")

if __name__ == "__main__":
    # --- CONFIGURACIÓN DE LA MISIÓN ---
    # Acá podés poner tantas URLs como quieras, con su cerebro de destino
    MISIONES = [
        {"url": "https://openai.com/research", "cerebro": "fuego"},
        {"url": "https://www.serviu.gob.cl/permisos-de-edificacion", "cerebro": "tierra"},
        # Podés agregar más abajo:
        # {"url": "https://otra-web.com", "cerebro": "aire"},
    ]

    for mision in MISIONES:
        url = mision["url"]
        cerebro = mision["cerebro"]
        
        texto = extraer_texto_web(url)
        if texto:
            analisis = analizar_conocimiento(texto, url)
            print("\n" + "="*50)
            print(f"🧠 ANÁLISIS PARA: {url}")
            print(analisis)
            print("="*50)
            
            guardar_en_cerebro(texto, url, cerebro)
