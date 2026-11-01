#!/usr/bin/env python3
"""Agente CEO: enruta una pregunta y consulta los coaches vectoriales en Supabase."""

import argparse
import json
import os
import re
import sys
import unicodedata
from pathlib import Path

import numpy as np
from dotenv import load_dotenv
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from sentence_transformers import SentenceTransformer
from supabase import create_client

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

MODELO_EMBEDDINGS = "intfloat/multilingual-e5-small"
CANTIDAD_RESULTADOS = 6

ELEMENTOS = {
    "Agua": ["coach_shopify"],
    "Aire": ["coach_rrss", "coach_pitches"],
    "Fuego": ["coach_python"],
    "Tierra": ["coach_tierra"],
    "Metal": ["coach_metal"],
    "Sence": ["coach_sence"],
}

ALIAS_ELEMENTOS = {
    "Os10": "Sence",
    "Os-10": "Sence",
    "Os 10": "Sence",
    "OS10": "Sence",
    "Sence": "Sence",
}

PALABRAS_CLAVE = {
    "Tierra": [
        "construccion", "construcción", "obra", "cubicacion", "cubicación",
        "hormigon", "hormigón", "oguc", "serviu", "terreno", "remodelacion",
    ],
    "Metal": [
        "legal", "ley", "contrato", "abogado", "sii", "cbr", "escritura",
        "demanda", "sociedad", "finanza", "contabilidad", "inversion", "inversión",
    ],
    "Aire": [
        "marketing", "venta", "vender", "pitch", "speech", "whatsapp", "cliente",
        "persuasion", "persuasión", "copywriting", "branding", "crm", "rrss",
        "redes sociales", "instagram", "reels", "tiktok", "anuncio", "publicidad",
    ],
    "Fuego": [
        "python", "codigo", "código", "script", "programacion", "programación",
        "ia", "automatizacion", "automatización", "agente", "prompt", "supabase",
    ],
    "Agua": [
        "dropshipping", "shopify", "ecommerce", "e-commerce", "tienda",
        "proveedor", "producto ganador", "logistica", "logística",
    ],
    "Sence": [
        "seguridad", "seguridad laboral", "seguridad y salud ocupacional",
        "salud ocupacional", "prevencion de riesgos", "higiene industrial",
        "ergonomia", "sst", "mutual de seguridad",
        "accidente laboral", "accidentes laborales", "riesgos", "evaluacion de riesgos",
        "os-10", "os 10", "os10", "d.s. 594", "d.s 594", "ds 594", "d.s. n° 594", "ds n° 594",
        "decreto 594", "decreto supremo 594", "ley 16.744", "ley 16744",
        "16.744", "16744", "curso sence", "sence",
    ],
}


def crear_llm():
    """LLM principal con cadena de fallbacks: OpenCode -> Moonshot -> OpenAI.

    Si OpenCode agota la cuota (429), Moonshot u OpenAI terminan la respuesta
    sin dejar la consulta caída (mismo patrón que usa mente_360.py).
    """
    principales = []
    if os.getenv("OPENCODE_API_KEY"):
        principales.append(
            ChatOpenAI(
                model="deepseek-v4-pro",
                temperature=0.2,
                api_key=os.getenv("OPENCODE_API_KEY"),
                base_url="https://opencode.ai/inference/go/openai/v1",
                max_retries=1,
                default_headers={
                    "x-opencode-session": "depafix-agente-ceo-final",
                    "User-Agent": "DepaFix-AgenteCEO/1.0",
                },
            )
        )
    respaldos = []
    if os.getenv("MOONSHOT_API_KEY"):
        respaldos.append(
            ChatOpenAI(
                model=os.getenv("AGENTE_CEO_MODELO", "kimi-k2-0905-preview"),
                temperature=0.2,
                api_key=os.getenv("MOONSHOT_API_KEY"),
                base_url=os.getenv("MOONSHOT_BASE_URL", "https://api.moonshot.ai/v1"),
                max_retries=1,
            )
        )
    if os.getenv("OPENAI_API_KEY"):
        respaldos.append(
            ChatOpenAI(
                model="gpt-4o-mini",
                temperature=0.2,
                api_key=os.getenv("OPENAI_API_KEY"),
                max_retries=1,
            )
        )
    if not principales and not respaldos:
        raise SystemExit(
            "Falta OPENCODE_API_KEY, MOONSHOT_API_KEY u OPENAI_API_KEY en el .env"
        )
    if not principales:
        llm = respaldos.pop(0)
        return llm.with_fallbacks(respaldos) if respaldos else llm
    # Los respaldos deben correr aunque el principal culpee la cuota (429).
    for respaldo in respaldos:
        respaldo.max_retries = 0
    return principales[0].with_fallbacks(respaldos)


def crear_supabase():
    url = os.getenv("SUPABASE_URL", "").strip()
    key = (
        os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
        or os.getenv("SUPABASE_KEY", "").strip()
    )
    if not url or not key:
        raise SystemExit("Faltan SUPABASE_URL y SUPABASE_SERVICE_ROLE_KEY en el .env")
    return create_client(url, key)


def normalizar(texto):
    texto = texto.lower()
    texto = unicodedata.normalize("NFD", texto)
    return "".join(caracter for caracter in texto if unicodedata.category(caracter) != "Mn")


def coincide_palabra(texto, palabra):
    patron = rf"(?<!\w){re.escape(normalizar(palabra))}(?!\w)"
    return re.search(patron, normalizar(texto)) is not None


def detectar_por_palabras(pregunta):
    detectadas = []
    texto = pregunta.lower()
    for elemento, palabras in PALABRAS_CLAVE.items():
        if any(coincide_palabra(texto, palabra) for palabra in palabras):
            detectadas.append(elemento)
    if "rrss" in texto or "redes sociales" in texto:
        detectadas = [elemento for elemento in detectadas if elemento != "Agua"]
        if "Aire" not in detectadas:
            detectadas.append("Aire")
    return detectadas


def enrutar_pregunta(llm, pregunta):
    prompt = """
    Eres el Router del Agente CEO de DepaFix. Clasifica la pregunta en uno o más elementos:
    - Agua: dropshipping, Shopify, e-commerce, productos, proveedores, logística.
    - Aire: marketing, ventas, copywriting, pitches, WhatsApp, anuncios, branding, CRM y RRSS/redes sociales.
    - Fuego: IA, Python, programación, automatización, agentes, datos/RAG, prompts.
    - Tierra: construcción, obras, cubicación, presupuestos, normativas OGUC/SERVIU.
    - Metal: legal, contratos, leyes, finanzas, inversión, contabilidad, SII, CBR.
    - Sence: seguridad y salud ocupacional, seguridad laboral, prevención de riesgos, OS-10, D.S. 594, Ley 16.744, cursos SENCE.

    Si la pregunta trata sobre seguridad, OS-10, D.S. 594, Ley 16.744 o cursos SENCE,
    clasifícala como Sence aunque mencione leyes, normativas o aspectos legales.

    Responde SOLO con el nombre del elemento principal (Agua, Aire, Fuego, Tierra, Metal o Sence).
    Si combina dominios, sepáralos por comas. No agregues explicaciones.

    Pregunta: {pregunta}
    """
    detectadas = detectar_por_palabras(pregunta)
    if "Sence" in detectadas:
        # Seguridad laboral, OS10, SENCE, D.S. 594 y Ley 16.744 van a coach_sence.
        return ["Sence"]
    try:
        chain = PromptTemplate(template=prompt, input_variables=["pregunta"]) | llm | StrOutputParser()
        resultado = chain.invoke({"pregunta": pregunta}).strip()
        areas = []
        for area in resultado.replace(" y ", ",").split(","):
            area = area.strip().capitalize()
            area = ALIAS_ELEMENTOS.get(area, area)
            if area in ELEMENTOS:
                areas.append(area)
        if areas:
            return list(dict.fromkeys(areas))
    except Exception as error:
        print(f"  ⚠️ Router LLM falló ({error}); usando reglas por palabra clave.")

    return detectadas or ["Aire"]


def extraer_texto(fila):
    for campo in ("contenido", "content", "texto"):
        valor = fila.get(campo)
        if valor:
            return str(valor).strip()
    return ""


def buscar_tabla_directo(cliente, tabla, vector):
    """Respaldo local si la función RPC todavía no existe en Supabase."""
    respuesta = (
        cliente.table(tabla)
        .select("contenido,metadata,embedding")
        .limit(1000)
        .execute()
    )
    filas = respuesta.data or []
    consulta = np.asarray(vector, dtype=float)
    norma_consulta = np.linalg.norm(consulta)
    puntuados = []
    for fila in filas:
        texto = extraer_texto(fila)
        if not texto:
            continue
        embedding = fila.get("embedding")
        similitud = 0.0
        if embedding is not None and norma_consulta > 0:
            try:
                if isinstance(embedding, str):
                    embedding = json.loads(embedding)
                documento = np.asarray(embedding, dtype=float)
                denominador = norma_consulta * np.linalg.norm(documento)
                if denominador > 0:
                    similitud = float(np.dot(consulta, documento) / denominador)
            except (TypeError, ValueError, json.JSONDecodeError):
                similitud = 0.0
        puntuados.append((similitud, texto, fila.get("metadata") or {}))
    puntuados.sort(key=lambda item: item[0], reverse=True)
    return [
        {"contenido": texto, "metadata": metadata, "similitud": similitud}
        for similitud, texto, metadata in puntuados[:CANTIDAD_RESULTADOS]
    ]


def consultar_rpc(cliente, tabla, vector, k=CANTIDAD_RESULTADOS):
    rpc = f"match_{tabla}"
    try:
        respuesta = cliente.rpc(
            rpc,
            {
                "query_embedding": vector,
                "match_threshold": 0.0,
                "match_count": k,
            },
        ).execute()
        filas = respuesta.data or []
        return [
            {
                "contenido": extraer_texto(fila),
                "metadata": fila.get("metadata") or {},
                "similitud": fila.get("similarity"),
            }
            for fila in filas
            if extraer_texto(fila)
        ]
    except Exception as error:
        print(f"  ⚠️ RPC {rpc} no disponible ({str(error)[:120]}).")
        print("  🔁 Usando búsqueda directa sobre la tabla...")
        return buscar_tabla_directo(cliente, tabla, vector)


def construir_contexto(resultados):
    bloques = []
    for elemento, tabla, fragmentos in resultados:
        for indice, fila in enumerate(fragmentos, start=1):
            bloques.append(
                f"[Elemento: {elemento} | Tabla: {tabla} | Fragmento {indice}]\n"
                f"{fila['contenido']}"
            )
    return "\n\n".join(bloques)


def responder(llm, pregunta, elementos, contexto):
    prompt = """
    Eres el Agente CEO de DepaFix. Respondes con criterio técnico y comercial,
    usando exclusivamente el contexto recuperado de los coaches.

    Reglas:
    - No inventes cifras, leyes, tasas ni casos de éxito.
    - Si el contexto no alcanza, dilo y pide el dato faltante.
    - Entrega una respuesta directa, accionable y en español.
    - Si corresponde, incluye pasos concretos y una recomendación final.

    Elementos consultados: {elementos}

    Contexto recuperado:
    {contexto}

    Pregunta: {pregunta}

    Respuesta:
    """
    chain = (
        PromptTemplate(
            template=prompt,
            input_variables=["elementos", "contexto", "pregunta"],
        )
        | llm
        | StrOutputParser()
    )
    return chain.invoke(
        {
            "elementos": ", ".join(elementos),
            "contexto": contexto,
            "pregunta": pregunta,
        }
    )


def ejecutar(pregunta, llm, cliente, modelo_embeddings):
    print("🧭 Enrutando la pregunta...")
    elementos = enrutar_pregunta(llm, pregunta)
    print(f"🎯 Elemento(s): {', '.join(elementos)}")

    vector = modelo_embeddings.encode(
        f"query: {pregunta}", normalize_embeddings=True
    ).tolist()

    resultados = []
    for elemento in elementos:
        for tabla in ELEMENTOS[elemento]:
            fragmentos = consultar_rpc(cliente, tabla, vector)
            resultados.append((elemento, tabla, fragmentos))
            print(f"  🔎 {tabla}: {len(fragmentos)} fragmentos")

    if not any(fragmentos for _, _, fragmentos in resultados):
        return "No encontré contexto en Supabase para esta pregunta.", elementos

    contexto = construir_contexto(resultados)
    print("🤔 Redactando respuesta final...")
    return responder(llm, pregunta, elementos, contexto), elementos


def main():
    parser = argparse.ArgumentParser(description="Agente CEO de DepaFix")
    parser.add_argument("pregunta", nargs="*", help="Pregunta a responder")
    args = parser.parse_args()

    llm = crear_llm()
    cliente = crear_supabase()
    print("🧠 Cargando modelo de embeddings...")
    modelo_embeddings = SentenceTransformer(MODELO_EMBEDDINGS)

    pregunta = " ".join(args.pregunta).strip()
    if pregunta:
        respuesta, _ = ejecutar(pregunta, llm, cliente, modelo_embeddings)
        print("\n" + "=" * 60)
        print(respuesta)
        print("=" * 60)
        return

    while True:
        try:
            pregunta = input("\n💬 Pregunta (o 'salir'): ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if pregunta.lower() in ["salir", "exit", "quit"]:
            break
        if not pregunta:
            continue
        respuesta, _ = ejecutar(pregunta, llm, cliente, modelo_embeddings)
        print("\n" + "=" * 60)
        print(respuesta)
        print("=" * 60)


if __name__ == "__main__":
    main()
