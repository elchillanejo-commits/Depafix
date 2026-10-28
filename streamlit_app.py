import streamlit as st
import os
from openai import OpenAI
from dotenv import load_dotenv
from knowledge.query import query_knowledge

# Cargar variables de entorno
load_dotenv()

MOONSHOT_KEY = os.environ.get("MOONSHOT_API_KEY") or os.environ.get("OPENAI_API_KEY")
MODEL_NAME = os.environ.get("LLM_MODEL", "kimi-k3.1-pro")

# Configuración de página
st.set_page_config(page_title="DepaFix Knowledge Core", page_icon="🧠", layout="wide")
st.title("🧠 DepaFix Knowledge Core")
st.markdown("Consulta inteligente sobre tus documentos de marketing y trading.")

# Barra lateral
with st.sidebar:
    st.header("Filtros")
    domain_opt = st.selectbox("Dominio", ["Todos", "marketing", "trading"])
    domain = None if domain_opt == "Todos" else domain_opt
    
    if st.button("Limpiar chat"):
        st.session_state.messages = []
        st.rerun()

# Inicializar estado de la sesión
if "messages" not in st.session_state:
    st.session_state.messages = []

# Mostrar historial de mensajes
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if "citations" in msg:
            for cit in msg["citations"]:
                with st.expander(f"Fuente: {cit.get('source_file', 'Desconocido')} (Similitud: {cit.get('score', 0):.2f})"):
                    st.write(cit.get("content", ""))

# Input del usuario
if prompt := st.chat_input("Haz una pregunta sobre tus manuales..."):
    # Guardar y mostrar mensaje del usuario
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Generar respuesta
    with st.chat_message("assistant"):
        with st.spinner("Buscando en el Knowledge Core..."):
            try:
                # 1. Buscar fragmentos
                chunks = query_knowledge(prompt, domain=domain, n=3)
                
                contexto = ""
                for i, c in enumerate(chunks):
                    contexto += f"\n--- Fragmento {i+1} ---\n{c.get('content', '')}\n"
                
                # 2. Llamar a Kimi
                if not MOONSHOT_KEY:
                    st.error("Falta MOONSHOT_API_KEY en el .env")
                else:
                    llm = OpenAI(api_key=MOONSHOT_KEY, base_url="https://api.moonshot.ai/v1")
                    
                    response = llm.chat.completions.create(
                        model=MODEL_NAME,
                        messages=[
                            {"role": "system", "content": "Responde basándote ESTRICTAMENTE en el siguiente contexto. Si no está, di que no lo sabes."},
                            {"role": "user", "content": f"Contexto:\n{contexto}\n\nPregunta: {prompt}"}
                        ],
                        temperature=1.0
                    )
                    
                    respuesta = response.choices[0].message.content
                    st.markdown(respuesta)
                    
                    # 3. Mostrar citas
                    for cit in chunks:
                        with st.expander(f"Fuente: {cit.get('source_file', 'Desconocido')} (Similitud: {cit.get('score', 0):.2f})"):
                            st.write(cit.get("content", ""))
                    
                    # Guardar en historial
                    st.session_state.messages.append({
                        "role": "assistant", 
                        "content": respuesta,
                        "citations": chunks
                    })
            except Exception as e:
                st.error(f"Error en el proceso: {e}")
