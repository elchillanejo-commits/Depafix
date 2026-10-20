"""
prompt_engineer.py — Ingeniería de Prompts para la Agencia Ikki.
Estructura el conocimiento del RAG para inyectarlo a un LLM real (Kimi/OpenAI).
"""

def construir_prompt(rubro: str, cliente: str, contexto_rag: str) -> list[dict]:
    """Genera el payload de mensajes (System + User) listo para la API del LLM."""
    
    system_prompt = f"""Eres "Ikki", el Director Creativo de una agencia de marketing de alto rendimiento.
Tu único objetivo es escribir anuncios publicitarios de alta conversión basados en datos reales.

### CONTEXTO DE CONOCIMIENTO (Marketing y Ads):
{contexto_rag}

### INSTRUCCIONES CRÍTICAS:
1. Basándote ÚNICAMENTE en el contexto de conocimiento anterior, redacta 1 anuncio altamente persuasivo para el rubro del cliente.
2. Debes devolver ESTRICTAMENTE un objeto JSON, sin formato markdown (sin bloques ```json ... ```), sin explicaciones previas ni posteriores.
3. El JSON debe tener exactamente las siguientes llaves: "titulo", "cuerpo", "cta".
"""

    user_prompt = f"""DATOS DEL CLIENTE:
- Rubro: {rubro}
- Cliente: {cliente}

### EJEMPLO DE SALIDA ESPERADA (Few-Shot Example):
{{
  "titulo": "Atrae más clientes hoy",
  "cuerpo": "Nuestro sistema automatizado te trae clientes calificados sin que gastes de más.",
  "cta": "Agenda aquí"
}}

### TU RESPUESTA:
"""

    # Formato estándar de la industria (compatible con Kimi, OpenAI, Anthropic)
    messages = [
        {"role": "system", "content": system_prompt.strip()},
        {"role": "user", "content": user_prompt.strip()}
    ]
    
    return messages
