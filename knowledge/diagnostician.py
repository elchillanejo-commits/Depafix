#!/usr/bin/env python3
from __future__ import annotations
import os
import logging
from openai import OpenAI
from dotenv import load_dotenv
from knowledge.query import query_knowledge

load_dotenv()
logging.basicConfig(level=logging.WARNING)

MOONSHOT_KEY = os.environ.get("MOONSHOT_API_KEY") or os.environ.get("OPENAI_API_KEY")
MODEL_NAME = os.environ.get("LLM_MODEL", "kimi-k3.1-pro")

def diagnosticar_error(error_log: str, domain: str | None = None) -> str:
    """
    Recibe un string con el error del sistema, busca en el Knowledge Core
    y devuelve un diagnóstico/solución.
    """
    print(f"🔍 Diagnostigando error en el Knowledge Core...")
    
    # Buscar posibles soluciones en la base de datos
    chunks = query_knowledge(error_log, domain=domain, n=3)
    
    if not chunks:
        return "⚠️ No se encontró información sobre este error en los manuales."

    contexto = ""
    for i, c in enumerate(chunks):
        contexto += f"\n--- Fragmento {i+1} (Fuente: {c.get('source_file', 'Desconocido')}) ---\n"
        contexto += c.get('content', '') + "\n"

    llm = OpenAI(api_key=MOONSHOT_KEY, base_url="https://api.moonshot.ai/v1")
    
    prompt = f"""
    Eres un Ingeniero de Sistemas experto. Ocurrió el siguiente error en producción:
    {error_log}

    Basándote ESTRICTAMENTE en los siguientes fragmentos de nuestros manuales técnicos, 
    redacta un diagnóstico de la causa probable y los pasos exactos para solucionarlo.
    Si los manuales no contienen la solución, indícalo claramente.

    Contexto de los manuales:
    {contexto}
    """

    response = llm.chat.completions.create(
        model=MODEL_NAME,
        messages=[{"role": "user", "content": prompt}],
        temperature=1.0,
        max_tokens=1000
    )

    return response.choices[0].message.content.strip()
