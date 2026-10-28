#!/usr/bin/env python3
from __future__ import annotations
import os
import sys
import logging
from openai import OpenAI
from dotenv import load_dotenv

# Importamos la función de búsqueda que ya tienes creada
from knowledge.query import query_knowledge

load_dotenv()
logging.basicConfig(level=logging.WARNING)  # Ocultar logs ruidosos de httpx

MOONSHOT_KEY = os.environ.get("MOONSHOT_API_KEY") or os.environ.get("OPENAI_API_KEY")
MODEL_NAME = os.environ.get("LLM_MODEL", "kimi-k3.1-pro")

def main():
    if len(sys.argv) < 2:
        print("Uso: python knowledge/chat_knowledge.py \"Tu pregunta aquí\" [--domain marketing|trading]")
        return

    pregunta = sys.argv[1]
    domain = None
    if "--domain" in sys.argv:
        idx = sys.argv.index("--domain")
        if idx + 1 < len(sys.argv):
            domain = sys.argv[idx + 1]

    print(f"\n🔍 Buscando contexto para: '{pregunta}'...")
    
    # 1. Buscar en la base de datos (los 3 fragmentos más relevantes)
    chunks = query_knowledge(pregunta, domain=domain, n=3)
    
    if not chunks:
        print("❌ No se encontró contexto relevante en la base de datos.")
        return

    # 2. Construir el contexto para el LLM
    contexto = ""
    for i, c in enumerate(chunks):
        contexto += f"\n--- Fragmento {i+1} (Fuente: {c.get('source_file', 'Desconocido')}) ---\n"
        contexto += c.get('content', '') + "\n"
    
    print(f"✅ {len(chunks)} fragmentos encontrados. Pensando respuesta...\n")

    # 3. Llamar al LLM (Kimi/Moonshot)
    if not MOONSHOT_KEY:
        print("❌ Error: Falta la API KEY en el .env")
        return

    llm = OpenAI(api_key=MOONSHOT_KEY, base_url="https://api.moonshot.ai/v1")
    
    prompt_sistema = (
        "Eres un asistente experto. Responde a la pregunta del usuario "
        "basándote ESTRICTAMENTE en los fragmentos de texto proporcionados. "
        "Si la información no está en el texto, di 'No tengo información sobre eso en mis documentos'. "
        "Sé directo, estructurado y no inventes información."
    )
    
    prompt_usuario = f"Contexto recuperado:\n{contexto}\n\nPregunta: {pregunta}"

    try:
        response = llm.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": prompt_sistema},
                {"role": "user", "content": prompt_usuario}
            ],
            temperature=1.0,  # KIMI SOLO ACEPTA 1.0
            max_tokens=1500
        )

        print("🤖 RESPUESTA DEL CHAT RAG:")
        print("=" * 60)
        
        # Validar que la respuesta no venga vacía
        respuesta_texto = response.choices[0].message.content
        if respuesta_texto and respuesta_texto.strip():
            print(respuesta_texto.strip())
        else:
            print("[El modelo no devolvió texto. Intenta de nuevo o cambia la pregunta.]")
        
        print("=" * 60)

    except Exception as e:
        print(f"❌ Error al conectar con el LLM: {e}")

if __name__ == "__main__":
    main()
