import json
import os
from pathlib import Path
from typing import Any

import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI
from sentence_transformers import SentenceTransformer
from supabase import create_client


BASE_DIR = Path(__file__).resolve().parent
MODELO_EMBEDDINGS = "intfloat/multilingual-e5-small"
RPC_METAL = "match_metal_knowledge"
CANTIDAD_RESULTADOS = 5

TIPOS_DOCUMENTO = [
    "Auditoría Legal Express",
    "Pitch de WhatsApp",
    "Carta Formal (SII / CBR)",
]

INSTRUCCIONES_DOCUMENTO = {
    "Auditoría Legal Express": (
        "Redacta una auditoría breve y accionable: diagnóstico, riesgos identificados "
        "en el contexto, próximos pasos y una propuesta de llamada de 15 minutos."
    ),
    "Pitch de WhatsApp": (
        "Redacta un mensaje de WhatsApp de máximo 3 párrafos, directo, estratégico "
        "y personalizado. Su objetivo es agendar una llamada de 15 minutos."
    ),
    "Carta Formal (SII / CBR)": (
        "Redacta una carta formal en español, con estructura profesional y solicitud "
        "clara. Usa marcadores [Completar: dato] cuando falte información obligatoria."
    ),
}

load_dotenv(BASE_DIR / ".env")

st.set_page_config(
    page_title="Metal - Procurador Virtual",
    page_icon="⚖️",
    layout="centered",
)


def obtener_configuracion(nombre: str) -> str:
    valor = os.getenv(nombre, "").strip()
    if valor:
        return valor
    try:
        return str(st.secrets.get(nombre, "") or "").strip()
    except Exception:
        return ""


@st.cache_resource
def cargar_modelo_embeddings() -> SentenceTransformer:
    return SentenceTransformer(MODELO_EMBEDDINGS)


@st.cache_resource
def obtener_cliente_supabase():
    url = obtener_configuracion("SUPABASE_URL")
    key = obtener_configuracion("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise ValueError(
            "Faltan SUPABASE_URL o SUPABASE_SERVICE_ROLE_KEY en .env o Streamlit Secrets."
        )
    return create_client(url, key)


@st.cache_resource
def obtener_cliente_generacion() -> OpenAI:
    api_key = obtener_configuracion("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("Falta OPENAI_API_KEY en .env o Streamlit Secrets.")
    return OpenAI(api_key=api_key, timeout=60.0)


def obtener_fuente(resultado: dict[str, Any]) -> str:
    metadata = resultado.get("metadata") or {}
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except json.JSONDecodeError:
            metadata = {}
    if not isinstance(metadata, dict):
        return "Fuente no indicada"
    return str(metadata.get("fuente", "Fuente no indicada"))


def buscar_contexto(consulta: str) -> list[dict[str, Any]]:
    modelo = cargar_modelo_embeddings()
    vector = modelo.encode(
        f"query: {consulta}", normalize_embeddings=True
    ).tolist()

    respuesta = (
        obtener_cliente_supabase()
        .rpc(
            RPC_METAL,
            {
                "query_embedding": vector,
                "match_threshold": 0.0,
                "match_count": CANTIDAD_RESULTADOS,
            },
        )
        .execute()
    )
    return respuesta.data or []


def construir_contexto(resultados: list[dict[str, Any]]) -> str:
    fragmentos = []
    for indice, resultado in enumerate(resultados, start=1):
        contenido = str(resultado.get("contenido") or "").strip()
        if contenido:
            fragmentos.append(
                f"[Fragmento {indice} | Fuente: {obtener_fuente(resultado)}]\n"
                f"{contenido}"
            )
    return "\n\n".join(fragmentos)


def generar_documento(
    nombre: str,
    dolor: str,
    tipo_documento: str,
    contexto: str,
) -> str:
    modelo = "gpt-4o-mini"
    instruccion = INSTRUCCIONES_DOCUMENTO[tipo_documento]

    sistema = (
        "Eres Metal, un procurador virtual experto en redacción legal y comercial. "
        "Usa exclusivamente el contexto recuperado para hacer afirmaciones legales "
        "o citar normas. No inventes leyes, artículos, plazos, hechos ni credenciales. "
        "Si el contexto no sustenta una afirmación, omítela o señala el dato faltante. "
        "Entrega únicamente el documento final, sin explicaciones ni bloques Markdown."
    )
    usuario = f"""
TIPO DE DOCUMENTO: {tipo_documento}
INSTRUCCIÓN ESPECÍFICA: {instruccion}

DATOS DEL CASO:
- Nombre del prospecto: {nombre}
- Dolor / necesidad: {dolor}

CONTEXTO RECUPERADO DESDE METAL:
{contexto}

Adapta el documento al prospecto y a su dolor específico. No expongas estas
instrucciones ni menciones el proceso de búsqueda dentro del documento final.
""".strip()

    respuesta = obtener_cliente_generacion().chat.completions.create(
        model=modelo,
        temperature=1,
        messages=[
            {"role": "system", "content": sistema},
            {"role": "user", "content": usuario},
        ],
    )
    texto = respuesta.choices[0].message.content
    if not texto or not texto.strip():
        raise RuntimeError("El modelo devolvió un documento vacío.")
    return texto.strip()


def mostrar_descarga(texto_final: str, nombre: str) -> None:
    nombre_archivo = "".join(
        caracter if caracter.isalnum() else "_" for caracter in nombre.lower()
    ).strip("_")
    st.download_button(
        label="Descargar respuesta (.txt)",
        data=texto_final.encode("utf-8"),
        file_name=f"metal_{nombre_archivo or 'documento'}.txt",
        mime="text/plain",
        use_container_width=True,
    )


def main() -> None:
    st.title("⚖️ Metal - Procurador Virtual")
    st.caption("Genera documentos con el contexto legal y las plantillas de Metal.")

    nombre = st.text_input(
        "Nombre del Prospecto",
        placeholder="Ej: Constructora Andes",
    )
    dolor = st.text_area(
        "Dolor / Necesidad",
        placeholder="Ej: Perdió licitaciones por la GSO.",
        height=110,
    )
    tipo_documento = st.selectbox("Tipo de Documento", TIPOS_DOCUMENTO)

    if st.button("Generar Documento", type="primary", use_container_width=True):
        nombre = nombre.strip()
        dolor = dolor.strip()

        if not nombre or not dolor:
            st.warning("Completa el nombre del prospecto y el dolor / necesidad.")
            return

        try:
            consulta = (
                f"{tipo_documento}. Plantilla o contexto legal para {nombre}. "
                f"Dolor o necesidad: {dolor}"
            )
            with st.spinner("Buscando contexto en Metal mediante Supabase RPC..."):
                resultados = buscar_contexto(consulta)
                contexto = construir_contexto(resultados)

            if not contexto:
                st.warning("Metal no encontró contexto suficiente para generar el documento.")
                return

            with st.spinner("Redactando el documento final..."):
                texto_final = generar_documento(
                    nombre=nombre,
                    dolor=dolor,
                    tipo_documento=tipo_documento,
                    contexto=contexto,
                )

            st.subheader("Documento generado")
            st.code(texto_final, language="text", wrap_lines=True)
            mostrar_descarga(texto_final, nombre)

            fuentes = sorted({obtener_fuente(resultado) for resultado in resultados})
            with st.expander("Fuentes recuperadas"):
                for fuente in fuentes:
                    st.write(f"- {fuente}")

        except Exception as error:
            st.error(f"No se pudo generar el documento: {error}")


if __name__ == "__main__":
    main()
