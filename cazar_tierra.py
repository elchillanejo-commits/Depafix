#!/usr/bin/env python3
"""Extrae criterios técnicos de construcción y cubicación y los agrega al cerebro Tierra."""

import argparse
import os
import re
from pathlib import Path

import requests
import trafilatura
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from langchain_community.vectorstores import FAISS
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_openai import ChatOpenAI
from langchain_text_splitters import RecursiveCharacterTextSplitter


BASE_DIR = Path(__file__).resolve().parent
RUTA_FAISS = BASE_DIR / "data" / "tierra.faiss"
MODELO_EMBEDDINGS = "sentence-transformers/all-MiniLM-L6-v2"
MIN_CARACTERES = 500
MAX_CARACTERES_LLM = 40000
TIMEOUT_HTTP = 30

load_dotenv(BASE_DIR / ".env")


def extraer_texto_web(url):
    """Descarga una URL y devuelve su texto visible, sin scripts ni estilos."""
    print(f"\nAnalizando: {url}")
    respuesta = requests.get(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0 Safari/537.36"
            ),
            "Accept-Language": "es-CL,es;q=0.9,en-US;q=0.8,en;q=0.7",
        },
        timeout=TIMEOUT_HTTP,
    )
    respuesta.raise_for_status()

    texto = trafilatura.extract(
        respuesta.text,
        include_comments=False,
        include_tables=True,
    )
    if not texto:
        soup = BeautifulSoup(respuesta.text, "html.parser")
        for elemento in soup(["script", "style", "noscript", "template"]):
            elemento.decompose()
        texto = soup.get_text(" ", strip=True)

    texto = re.sub(r"\s+", " ", texto).strip()
    if len(texto) < MIN_CARACTERES:
        raise ValueError(
            f"Texto insuficiente: {len(texto)} caracteres; mínimo {MIN_CARACTERES}."
        )

    frases_peligrosas = [
        "ignora las instrucciones",
        "ignore previous instructions",
        "system prompt",
        "olvida todo",
    ]
    patron = re.compile("|".join(map(re.escape, frases_peligrosas)), re.IGNORECASE)
    texto = patron.sub("[TEXTO ELIMINADO]", texto)
    print(f"Texto extraído: {len(texto)} caracteres.")
    return texto


def crear_llm():
    openai_key = os.getenv("OPENAI_API_KEY")
    if openai_key:
        return ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0.1,
            api_key=openai_key,
        )
    moonshot_key = os.getenv("MOONSHOT_API_KEY")
    if moonshot_key:
        return ChatOpenAI(
            model="kimi-k3.1-pro",
            temperature=1,
            api_key=moonshot_key,
            base_url=os.getenv("MOONSHOT_BASE_URL", "https://api.moonshot.ai/v1"),
        )
    raise RuntimeError("Falta OPENAI_API_KEY o MOONSHOT_API_KEY en el entorno o en .env.")


def resumir_criterios_duros(texto, url, llm):
    """Sintetiza solo criterios técnicos comprobables presentes en la fuente."""
    prompt = """
    Eres un Ingeniero de Datos Senior especializado en construcción, cubicación de obras y normativa de edificación en Chile.

    Extrae y resume en español los CRITERIOS TÉCNICOS Y REGLAS ACCIONABLES de construcción,
    cálculo/cubicación de materiales y permisos de edificación, usando exclusivamente el texto de referencia suministrado.

    Organiza el resultado con estas secciones:
    1. Cálculo y cubicación de materiales: fórmulas, unidades geométricas (m, m2, m3, kg), partidas de obra (excavación, fundaciones, hormigón, albañilería, tabiquería, techumbre, terminaciones) y dosificaciones.
    2. Rendimientos, pérdidas y presupuesto: porcentajes de pérdida/merma de materiales, análisis de precios unitarios (APU), costos directos e indirectos.
    3. Normativa y permisos de edificación (Chile / OGUC / LGUC / DOM / NCh 353): requisitos para obra nueva, obra menor y ampliaciones de vivienda, documentos y profesionales exigidos.
    4. Materiales y especificaciones técnicas: propiedades, clasificación y criterios de uso en obra.
    5. Reglas paso a paso: secuencia práctica para cubicar y planificar una obra o ampliación.

    Conserva cifras, fórmulas, normas (como NCh 353, OGUC, LGUC), tablas de dosificación/mermas y condiciones exactas cuando existan.
    No inventes datos ni completes vacíos con conocimiento externo.
    Si una sección no tiene criterios concretos en la fuente, indícalo en una sola línea.
    Extensión máxima total: 2800 caracteres. Sé denso y conciso; prioriza
    fórmulas, métricas y reglas accionables por encima de explicaciones genéricas.

    URL de la fuente: {url}

    Contenido web:
    <contenido_web>
    {texto}
    </contenido_web>
    """
    chain = (
        PromptTemplate(template=prompt, input_variables=["url", "texto"])
        | llm
        | StrOutputParser()
    )
    return chain.invoke({"url": url, "texto": texto[:MAX_CARACTERES_LLM]}).strip()


def crear_fragmentos(resumen, url):
    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    texto_con_fuente = (
        "Criterios técnicos de construcción, cálculo de materiales, cubicación y permisos en Chile.\n"
        f"Fuente: {url}\n\n{resumen}"
    )
    return splitter.create_documents(
        [texto_con_fuente],
        metadatas=[
            {
                "source": url,
                "fuente": url,
                "elemento": "tierra",
                "tipo": "criterios_duros_web",
            }
        ],
    )


def agregar_a_tierra(documentos):
    """Agrega documentos al índice existente y confirma el incremento sin borrar lo previo."""
    if not RUTA_FAISS.is_dir():
        raise FileNotFoundError(f"No existe el cerebro Tierra en {RUTA_FAISS}")

    embeddings = HuggingFaceEmbeddings(model_name=MODELO_EMBEDDINGS)
    vectorstore = FAISS.load_local(
        str(RUTA_FAISS),
        embeddings,
        allow_dangerous_deserialization=True,
    )
    cantidad_anterior = vectorstore.index.ntotal
    ids_anteriores = set(vectorstore.docstore._dict)

    ids_nuevos = vectorstore.add_documents(documentos)
    if not ids_anteriores.issubset(vectorstore.docstore._dict):
        raise RuntimeError("La incorporación alteró documentos existentes; no se guardó.")
    if vectorstore.index.ntotal != cantidad_anterior + len(ids_nuevos):
        raise RuntimeError("El conteo posterior no coincide; no se guardó.")

    vectorstore.save_local(str(RUTA_FAISS))
    print(f"Fragmentos anteriores: {cantidad_anterior}")
    print(f"Fragmentos nuevos agregados: {len(ids_nuevos)}")
    print(f"Total actual: {vectorstore.index.ntotal}")
    return len(ids_nuevos)


def main():
    parser = argparse.ArgumentParser(
        description="Agrega criterios técnicos de construcción al cerebro Tierra."
    )
    parser.add_argument("urls", nargs="+", help="URLs de guías técnicas de construcción")
    args = parser.parse_args()

    llm = crear_llm()
    documentos = []
    urls_exitosas = 0
    urls_fallidas = 0

    for url in dict.fromkeys(args.urls):
        try:
            texto = extraer_texto_web(url)
            print("Resumiendo criterios técnicos con el LLM...")
            resumen = resumir_criterios_duros(texto, url, llm)
            if not resumen:
                raise ValueError("El LLM devolvió un resumen vacío.")
            fragmentos = crear_fragmentos(resumen, url)
            documentos.extend(fragmentos)
            urls_exitosas += 1
            print(f"Resumen generado: {len(fragmentos)} fragmentos para {url}")
            print(resumen)
        except Exception as error:
            urls_fallidas += 1
            print(f"FALLIDA: {url} | {error}")

    print(
        f"\nResultado de extracción: {urls_exitosas} exitosas, "
        f"{urls_fallidas} fallidas."
    )
    if not documentos:
        print("No hay documentos nuevos; el índice no fue modificado.")
        return 1

    agregar_a_tierra(documentos)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
