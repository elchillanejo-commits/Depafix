import json
import os
import numpy as np
from dotenv import load_dotenv
from supabase import create_client
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser

load_dotenv()

# ==========================================
# CONFIGURACIÓN PARA OPENCODE GO (Plan $10)
# ==========================================
_opencode_llm = ChatOpenAI(
    model="deepseek-v4-pro",  # Modelo recomendado por la doc de OpenCode Go
    temperature=0.2,
    api_key=os.getenv("OPENCODE_API_KEY"),
    base_url="https://opencode.ai/inference/go/openai/v1",  # <-- URL CORRECTA
    timeout=25,
    max_retries=1,
    default_headers={
        "x-opencode-session": "depafix-mente360",
        "User-Agent": "mente360-rag/1.0"
    }
)
if os.getenv("OPENAI_API_KEY"):
    _fallback_llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0.2,
        api_key=os.getenv("OPENAI_API_KEY"),
    )
    llm = _opencode_llm.with_fallbacks([_fallback_llm])
else:
    llm = _opencode_llm

# ==========================================
# CONFIGURACIÓN DEL ROUTER HÍBRIDO Y JERARQUÍA
# ==========================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CARPETA_PROFESORES = os.path.join(BASE_DIR, "profesores")

# 1. Archivos FAISS Locales (Construcción y Legal)
CEREBROS_LOCALES = {
    "Tierra": "./data/tierra.faiss",  # Construcción
    "Metal": "./data/metal.faiss",    # Legal
}

# 2. Tablas en Supabase (Marketing/RRSS, Python y Dropshipping)
TABLAS_SUPABASE = {
    "Aire": ("coach_pitches", "coach_rrss"),  # Marketing / Ventas / RRSS
    "Fuego": ("coach_python",),               # Python / Tecnología
    "Agua": ("coach_shopify",),               # Dropshipping / E-commerce
}

# 3. Jerarquía de Profesores y sus 5 Coaches por Elemento
COACHES_POR_ELEMENTO = {
    "Agua": [
        "Coach Shopify",
        "Coach Productos",
        "Coach Proveedores",
        "Coach Logística",
        "Coach Ads E-commerce",
    ],
    "Aire": [
        "Coach Ventas",
        "Coach Copywriting",
        "Coach Anuncios",
        "Coach Branding",
        "Coach CRM",
    ],
    "Fuego": [
        "Coach Python",
        "Coach Automatización",
        "Coach Agentes IA",
        "Coach Datos",
        "Coach Prompts",
    ],
    "Tierra": [
        "Coach Construcción",
        "Coach Cubicación",
        "Coach Presupuestos",
        "Coach Normativas",
        "Coach Proveedores de Obra",
    ],
    "Metal": [
        "Coach Legal",
        "Coach Finanzas",
        "Coach Inversión",
        "Coach Contabilidad",
        "Coach Contratos",
    ],
}

TODAS_LAS_AREAS = list(CEREBROS_LOCALES.keys()) + list(TABLAS_SUPABASE.keys())


def cargar_cerebros():
    print("📥 Cargando modelo de embeddings local (Hugging Face)...")
    embeddings = HuggingFaceEmbeddings(model_name="intfloat/multilingual-e5-small")
    embeddings_alt = None
    cerebros_locales = {}

    print("🧠 Despertando Router Híbrido Mente 360...")
    # Cargar cerebros FAISS locales (Tierra y Metal)
    for nombre, ruta in CEREBROS_LOCALES.items():
        if os.path.exists(ruta):
            try:
                vs = FAISS.load_local(ruta, embeddings, allow_dangerous_deserialization=True)
                # Verificar dimensión del índice FAISS vs modelo de embeddings
                if hasattr(vs, "index") and vs.index.d != 384:
                    if embeddings_alt is None:
                        embeddings_alt = HuggingFaceEmbeddings(
                            model_name="sentence-transformers/all-MiniLM-L6-v2"
                        )
                    vs = FAISS.load_local(ruta, embeddings_alt, allow_dangerous_deserialization=True)
                cerebros_locales[nombre] = vs
                print(f"  ✅ [LOCAL FAISS] {nombre} conectado ({ruta}).")
            except Exception as e:
                print(f"  ⚠️ Error al cargar {nombre} local: {e}")
        else:
            print(f"  ❌ [LOCAL FAISS] {nombre} no encontrado en {ruta} (ignorado).")

    # Conectar cliente Supabase para Aire, Fuego y Agua
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")
    cliente_supabase = None
    if supabase_url and supabase_key:
        try:
            cliente_supabase = create_client(supabase_url, supabase_key)
            for area, tablas in TABLAS_SUPABASE.items():
                print(
                    f"  ☁️ [SUPABASE] {area} vinculado a tabla(s) "
                    f"{', '.join(tablas)}."
                )
        except Exception as e:
            print(f"  ⚠️ Error al conectar con Supabase: {e}")
    else:
        print("  ⚠️ Faltan SUPABASE_URL o SUPABASE_SERVICE_ROLE_KEY en .env (búsqueda cloud deshabilitada).")

    return {
        "locales": cerebros_locales,
        "supabase": cliente_supabase,
        "embeddings": embeddings,
    }


def leer_profesor_md(elemento):
    """Lee el archivo .md del Profesor Supervisor correspondiente al elemento."""
    nombre_archivo = f"{elemento.lower()}.md"
    rutas_posibles = [
        os.path.join("./profesores", nombre_archivo),
        os.path.join(CARPETA_PROFESORES, nombre_archivo),
    ]
    for ruta in rutas_posibles:
        if os.path.exists(ruta):
            try:
                with open(ruta, "r", encoding="utf-8") as f:
                    return f.read(), ruta
            except Exception as e:
                print(f"  ⚠️ Error leyendo {ruta}: {e}")
    return "", f"profesores/{nombre_archivo}"


def seleccionar_coach_con_profesor(elemento, pregunta):
    """El Profesor del elemento lee su archivo .md y decide qué Coach específico (de los 5 que supervisa) debe responder."""
    contenido_profesor, ruta_md = leer_profesor_md(elemento)
    coaches_disponibles = COACHES_POR_ELEMENTO.get(elemento, [])
    lista_coaches_str = ", ".join(coaches_disponibles)

    print(f"🎓 [PROFESOR {elemento.upper()}] Consultando directrices en '{ruta_md}'...")

    prompt_profesor = """
    {manual_profesor}

    ==========================================
    TAREA DE ASIGNACIÓN DE COACH (MODO CONSULTA):
    Actúa como el Profesor Supervisor del elemento {elemento}.
    Tienes bajo tu mando a estos 5 Coaches especialistas:
    {lista_coaches}

    Analiza la siguiente pregunta del usuario y decide cuál de tus 5 Coaches es el más indicado para responderla.
    Responde ÚNICAMENTE con el nombre exacto del Coach elegido (por ejemplo: "{ejemplo_coach}"). No agregues puntos ni explicaciones.

    Pregunta del usuario: {pregunta}
    """
    try:
        chain = (
            PromptTemplate(
                template=prompt_profesor,
                input_variables=["manual_profesor", "elemento", "lista_coaches", "ejemplo_coach", "pregunta"],
            )
            | llm
            | StrOutputParser()
        )
        respuesta_profesor = chain.invoke(
            {
                "manual_profesor": contenido_profesor or f"Profesor Supervisor del elemento {elemento}.",
                "elemento": elemento,
                "lista_coaches": lista_coaches_str,
                "ejemplo_coach": coaches_disponibles[0] if coaches_disponibles else "Coach",
                "pregunta": pregunta,
            }
        ).strip()

        for coach in coaches_disponibles:
            if coach.lower() in respuesta_profesor.lower():
                return coach, contenido_profesor
    except Exception as e:
        print(f"  ⚠️ Fallback de selección de Coach en {elemento} ({e})...")

    # Fallback heurístico por palabras clave para elegir entre los 5 Coaches del elemento
    pregunta_lower = pregunta.lower()
    keywords_coaches = {
        "Agua": {
            "Coach Productos": ["producto", "ganador", " saturacion", "saturación", "demanda", "margen", "validar"],
            "Coach Proveedores": ["proveedor", "aliexpress", "agente", "sourcing", "chino", "fabricante"],
            "Coach Logística": ["logistica", "logística", "envio", "envío", "aduana", "fulfillment", "entrega"],
            "Coach Ads E-commerce": ["ads", "anuncio", "campaña", "creativo", "roas", "cpa", "tiktok", "meta"],
            "Coach Shopify": ["shopify", "tienda", "checkout", "tema", "app", "configurar"],
        },
        "Aire": {
            "Coach Copywriting": ["copy", "guion", "guión", "pitch", "speech", "mensaje", "whatsapp", "redactar"],
            "Coach Anuncios": ["ads", "meta ads", "google ads", "anuncio", "campaña", "publico", "público", "ctr"],
            "Coach Branding": ["branding", "marca", "identidad", "posicionamiento", "narrativa"],
            "Coach CRM": ["crm", "pipeline", "seguimiento", "lead", "embudo"],
            "Coach Ventas": ["venta", "vender", "cierre", "objecion", "objeción", "prospecto", "reunion", "reunión"],
        },
        "Fuego": {
            "Coach Automatización": ["n8n", "make", "zapier", "cron", "automatizar", "automatización", "flujo", "webhook"],
            "Coach Agentes IA": ["agente", "orquestacion", "orquestación", "memoria", "tool", "arquitectura", "router"],
            "Coach Datos": ["faiss", "supabase", "embedding", "vector", "rag", "base de datos", "chunk"],
            "Coach Prompts": ["prompt", "system prompt", "alucinacion", "alucinación", "instruccion", "instrucción"],
            "Coach Python": ["python", "script", "codigo", "código", "libreria", "librería", "error", "bug"],
        },
        "Tierra": {
            "Coach Cubicación": ["cubicacion", "cubicación", "metraje", "m2", "m3", "rendimiento", "medicion", "medición"],
            "Coach Presupuestos": ["presupuesto", "apu", "costo", "precio", "cotizacion", "cotización", "margen"],
            "Coach Normativas": ["normativa", "oguc", "permiso", "municipal", "serviu", "ley", "seguridad", "licitacion", "licitación"],
            "Coach Proveedores de Obra": ["ferreteria", "ferretería", "material", "proveedor", "sodimac", "construmart"],
            "Coach Construcción": ["construccion", "construcción", "obra", "partida", "hormigon", "hormigón", "remodelacion"],
        },
        "Metal": {
            "Coach Finanzas": ["finanza", "flujo de caja", "margen", "impuesto", "iva", "renta", "tesoreria"],
            "Coach Inversión": ["inversion", "inversión", "ronda", "valuacion", "valuación", "capital", "inversionista"],
            "Coach Contabilidad": ["contabilidad", "contador", "boleta", "factura", "balance", "f29", "tributario"],
            "Coach Contratos": ["contrato", "clausula", "cláusula", "anexo", "acuerdo", "nda", "arriendo"],
            "Coach Legal": ["legal", "ley", "sii", "cbr", "sociedad", "spa", "escritura", "demanda", "abogado"],
        },
    }

    for coach, palabras in keywords_coaches.get(elemento, {}).items():
        if any(p in pregunta_lower for p in palabras):
            return coach, contenido_profesor

    coach_por_defecto = coaches_disponibles[0] if coaches_disponibles else f"Coach {elemento}"
    return coach_por_defecto, contenido_profesor


def enrutar_pregunta(pregunta):
    print("🧭 [1/3 ROUTER] Clasificando pregunta en uno de los 5 Elementos (Agua, Aire, Fuego, Tierra, Metal)...")
    pregunta_lower = pregunta.lower()

    prompt = """
    Eres el Router Principal de la Mente 360. Clasifica la pregunta del usuario en uno de los 5 elementos:
    - Agua: Dropshipping, Shopify, e-commerce, validación de productos, proveedores, logística (Supabase: coach_shopify)
    - Aire: Marketing, ventas, copywriting, pitches, WhatsApp, anuncios, branding, CRM y redes sociales/RRSS (Supabase: coach_pitches, coach_rrss)
    - Fuego: IA, Python, programación, código, automatización, agentes IA, datos/RAG, prompts (Supabase: coach_python)
    - Tierra: Construcción, obras, cubicación, presupuestos, normativas OGUC/SERVIU, materiales (Local: ./data/tierra.faiss)
    - Metal: Legal, contratos, leyes, finanzas, inversión, contabilidad, SII, CBR, sociedades (Local: ./data/metal.faiss)

    REGLA CLAVE:
    - Responde ÚNICAMENTE con el nombre del elemento principal (Agua, Aire, Fuego, Tierra o Metal).
    - Solo si la pregunta combina explícitamente más de un dominio, sepáralos por comas (ej: "Agua, Aire").

    Pregunta: {pregunta}
    """
    try:
        chain = PromptTemplate(template=prompt, input_variables=["pregunta"]) | llm | StrOutputParser()
        resultado = chain.invoke({"pregunta": pregunta}).strip()

        if "Todas" in resultado:
            return TODAS_LAS_AREAS

        areas = [c.strip() for c in resultado.split(",") if c.strip() in TODAS_LAS_AREAS]
        if areas:
            return areas
    except Exception as e:
        print(f"  ⚠️ Fallback a enrutamiento por palabras clave ({e})...")

    # Fallback heurístico si falla el LLM
    areas_detectadas = []
    reglas_keywords = {
        "Tierra": ["construccion", "construcción", "obra", "cubicacion", "cubicación", "hormigon", "hormigón", "ampliacion", "ampliación", "oguc", "serviu", "tierra"],
        "Metal": ["legal", "ley", "contrato", "abogado", "sii", "cbr", "escritura", "demanda", "sociedad", "finanza", "contabilidad", "inversion", "inversión", "metal"],
        "Aire": ["marketing", "venta", "vender", "pitch", "speech", "whatsapp", "cliente", "persuasion", "persuasión", "copywriting", "branding", "crm", "aire"],
        "Fuego": ["python", "codigo", "código", "script", "programacion", "programación", "ia", "automatizacion", "automatización", "agente", "prompt", "fuego"],
        "Agua": ["dropshipping", "shopify", "ecommerce", "e-commerce", "tienda", "proveedor", "producto ganador", "logistica", "logística", "agua"],
    }
    for area, palabras in reglas_keywords.items():
        if any(p in pregunta_lower for p in palabras):
            areas_detectadas.append(area)

    return areas_detectadas if areas_detectadas else ["Aire"]


def buscar_en_supabase(cliente_supabase, embeddings, tabla, pregunta, k=6):
    """Busca en la tabla correspondiente de Supabase (vía RPC vectorial o búsqueda en tabla)."""
    if not cliente_supabase:
        print(f"  ❌ Cliente Supabase no disponible para consultar '{tabla}'.")
        return []

    vector_pregunta = embeddings.embed_query(f"query: {pregunta}")

    # 1. Intentar búsqueda vectorial por RPC (match_<tabla>)
    try:
        rpc_name = f"match_{tabla}"
        res = cliente_supabase.rpc(
            rpc_name,
            {
                "query_embedding": vector_pregunta,
                "match_threshold": 0.0,
                "match_count": k,
            },
        ).execute()
        if res.data:
            return [
                fila.get("contenido") or fila.get("content") or fila.get("texto") or str(fila)
                for fila in res.data
            ]
    except Exception:
        pass

    # 2. Fallback: consultar registros de la tabla y ordenar por similitud coseno (si hay embedding)
    try:
        res = cliente_supabase.table(tabla).select("*").limit(1000).execute()
        filas = res.data or []
        if not filas:
            return []

        consulta_np = np.asarray(vector_pregunta, dtype=float)
        norma_consulta = np.linalg.norm(consulta_np)
        con_puntaje = []

        for fila in filas:
            emb = fila.get("embedding")
            texto = fila.get("contenido") or fila.get("content") or fila.get("texto") or ""
            if not texto:
                continue
            if emb is not None and norma_consulta > 0:
                try:
                    if isinstance(emb, str):
                        emb = json.loads(emb)
                    doc_np = np.asarray(emb, dtype=float)
                    denom = norma_consulta * np.linalg.norm(doc_np)
                    sim = float(np.dot(consulta_np, doc_np) / denom) if denom > 0 else 0.0
                    con_puntaje.append((sim, texto))
                    continue
                except Exception:
                    pass
            con_puntaje.append((0.0, texto))

        con_puntaje.sort(key=lambda item: item[0], reverse=True)
        return [texto for _, texto in con_puntaje[:k]]
    except Exception as e:
        print(f"  ⚠️ Error consultando tabla Supabase '{tabla}': {e}")
        return []


def consultar_mente_360(pregunta, recursos):
    if not recursos:
        return "No hay recursos cargados."

    cerebros_locales = recursos.get("locales", {})
    cliente_supabase = recursos.get("supabase")
    embeddings = recursos.get("embeddings")

    # 1. Router clasifica en uno (o más) de los 5 elementos
    areas_a_consultar = enrutar_pregunta(pregunta)
    print(f"🎯 Elemento(s) seleccionado(s): {', '.join(areas_a_consultar)}")

    # 2. Profesor de cada elemento lee su .md en profesores/ y asigna el Coach específico
    coaches_asignados = []
    profesores_activados = []
    for elemento in areas_a_consultar:
        coach_elegido, _ = seleccionar_coach_con_profesor(elemento, pregunta)
        coaches_asignados.append(f"{coach_elegido} (Elemento {elemento})")
        profesores_activados.append(f"Profesor Supervisor — Elemento {elemento} (profesores/{elemento.lower()}.md)")
        print(f"👨‍🏫 [2/3 PROFESOR {elemento}] Asignó a: {coach_elegido}")

    print("\n🔍 [3/3 COACH + RAG] Buscando información en el cerebro correspondiente...")
    contexto_combinado = ""

    fallbacks_locales_coaches = {
        "Aire": "./coaches/pitches/faiss_index/",
        "Fuego": "./coaches/python/faiss_index/",
    }

    for nombre in areas_a_consultar:
        # Ruta 1: Construcción (Tierra) o Legal (Metal) -> Archivos FAISS Locales
        if nombre in CEREBROS_LOCALES:
            if nombre in cerebros_locales:
                vs = cerebros_locales[nombre]
                resultados = vs.similarity_search(pregunta, k=6)
                for doc in resultados:
                    contexto_combinado += f"\n[Fuente Local FAISS: {nombre}]\n{doc.page_content}\n"
                print(f"  🔎 Búsqueda exitosa en archivo local {CEREBROS_LOCALES[nombre]} ({nombre})")
            else:
                print(f"  ⚠️ Índice local {CEREBROS_LOCALES[nombre]} no disponible.")

        # Ruta 2: Marketing/RRSS (Aire), Python (Fuego) o Dropshipping (Agua)
        # -> Tablas Supabase (con fallback FAISS local)
        elif nombre in TABLAS_SUPABASE:
            tablas = TABLAS_SUPABASE[nombre]
            encontrados = 0
            for tabla in tablas:
                fragmentos = buscar_en_supabase(
                    cliente_supabase, embeddings, tabla, pregunta, k=6
                )
                if fragmentos:
                    encontrados += len(fragmentos)
                    for fragmento in fragmentos:
                        contexto_combinado += (
                            f"\n[Fuente Supabase: {nombre} ({tabla})]\n"
                            f"{fragmento}\n"
                        )
                    print(
                        f"  🔎 Búsqueda exitosa en Supabase tabla '{tabla}' "
                        f"({nombre}: {len(fragmentos)} fragmentos)"
                    )
                else:
                    print(
                        f"  🔎 Consulta en Supabase tabla '{tabla}' "
                        f"({nombre}: 0 fragmentos)"
                    )

            if encontrados == 0:
                if (
                    nombre in fallbacks_locales_coaches
                    and os.path.exists(fallbacks_locales_coaches[nombre])
                ):
                    ruta_coach = fallbacks_locales_coaches[nombre]
                    vs_coach = FAISS.load_local(
                        ruta_coach, embeddings, allow_dangerous_deserialization=True
                    )
                    resultados = vs_coach.similarity_search(pregunta, k=4)
                    for doc in resultados:
                        contexto_combinado += (
                            f"\n[Fuente Local Coach FAISS: {nombre} "
                            f"({ruta_coach})]\n{doc.page_content}\n"
                        )
                    print(
                        f"  🔎 Tablas Supabase vacías; usando índice local "
                        f"{ruta_coach} ({nombre}: {len(resultados)} fragmentos)"
                    )
                else:
                    print(
                        f"  ⚠️ Sin fragmentos en Supabase para {nombre} "
                        "y sin fallback local."
                    )

    coaches_str = ", ".join(coaches_asignados)
    profesores_str = ", ".join(profesores_activados)
    print(f"🤔 Sintetizando respuesta como {coaches_str}...")

    prompt_template = """
    Eres el equipo de especialistas de la "Mente 360" de DepaFix.
    - Profesores Supervisores activados: {profesores}
    - Coaches especialistas asignados para responder: {coaches}

    INSTRUCCIONES DE RESPUESTA:
    - Inicia indicando brevemente qué Profesor(es) Supervisor(es) y qué Coach(es) específico(s) están respondiendo.
    - Combina el conocimiento técnico y comercial del contexto recuperado para entregar una respuesta accionable, directa, con datos duros y sin humo.
    - No inventes cifras, estadísticas ni casos de éxito. Usa solo el contexto recuperado; si falta un dato, dilo explícitamente.
    - Si el usuario pide redactar un Speech o mensaje de WhatsApp, entrégalo listo para enviar y adaptado al perfil solicitado (ej. Eneatipo).

    Contexto recuperado:
    {contexto}

    Pregunta: {pregunta}
    """

    chain = (
        PromptTemplate(
            template=prompt_template,
            input_variables=["profesores", "coaches", "contexto", "pregunta"],
        )
        | llm
        | StrOutputParser()
    )
    return chain.invoke(
        {
            "profesores": profesores_str,
            "coaches": coaches_str,
            "contexto": contexto_combinado,
            "pregunta": pregunta,
        }
    )


if __name__ == "__main__":
    if not os.getenv("OPENCODE_API_KEY") and not os.getenv("OPENAI_API_KEY"):
        print("❌ ERROR: Falta OPENCODE_API_KEY o OPENAI_API_KEY en .env")
        exit(1)

    mis_recursos = cargar_cerebros()
    print(
        f"✅ Recursos listos: {len(mis_recursos['locales'])} cerebros FAISS locales "
        f"| Supabase: {'conectado' if mis_recursos['supabase'] else 'desconectado'}.\n"
    )

    while True:
        try:
            pregunta = input("\n💬 Pregunta (o 'salir'): ")
        except EOFError:
            break
        if pregunta.lower() in ['salir', 'exit', 'quit']:
            break
        if not pregunta.strip():
            continue
        respuesta = consultar_mente_360(pregunta, mis_recursos)
        print("\n" + "="*50)
        print(respuesta)
        print("="*50)
