import os
import json
import sys
from dotenv import load_dotenv
from supabase import create_client
from sentence_transformers import SentenceTransformer

# langchain solo es necesario para el flujo conversacional (Router/Coach/Sintesis).
# Si no esta instalado, el modo --saldo-sence sigue funcionando.
try:
    from langchain_community.vectorstores import FAISS
except ImportError:
    FAISS = None
try:
    from langchain_huggingface import HuggingFaceEmbeddings
except ImportError:
    HuggingFaceEmbeddings = None
try:
    from langchain_openai import ChatOpenAI
except ImportError:
    ChatOpenAI = None
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser

load_dotenv()

# ==========================================
# CONFIGURACIÓN
# ==========================================
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

MODELO_EMBEDDINGS = "intfloat/multilingual-e5-small"

llm = None
if ChatOpenAI is not None and os.getenv("OPENCODE_API_KEY"):
    llm = ChatOpenAI(
        model="deepseek-v4-pro",
        temperature=0.2,
        api_key=os.getenv("OPENCODE_API_KEY"),
        base_url="https://opencode.ai/inference/go/openai/v1",
        default_headers={
            "x-opencode-session": "depafix-mente360",
            "User-Agent": "DepaFix-Mente360/1.0"
        }
    )


def _requerir_llm():
    """Devuelve el LLM o explica exactamente que falta para el flujo conversacional."""
    if llm is None:
        raise RuntimeError(
            "Flujo conversacional no disponible: instala langchain-openai "
            "(pip install langchain-openai) y define OPENCODE_API_KEY en .env."
        )
    return llm

# Seis elementos (ahora incluye SENCE)
ELEMENTOS = {
    "Agua":    {"desc": "Dropshipping, Shopify, importación, ventas e-commerce",          "tabla": "coach_shopify",  "local": None},
    "Aire":    {"desc": "Marketing digital, Meta Ads, RRSS, copywriting, pitches",         "tabla": ["coach_pitches", "coach_rrss"], "local": None},
    "Fuego":   {"desc": "Python, LangChain, FAISS, IA, OpenCode, automatización",          "tabla": "coach_python",   "local": None},
    "Tierra":  {"desc": "Construcción, cubicación, SERVIU, materiales, obra",              "tabla": "coach_tierra",   "local": "./data/tierra.faiss"},
    "Metal":   {"desc": "Legal, contratos, tributario, procurador, contabilidad",          "tabla": None,             "local": "./data/metal.faiss"},
    "Sence":   {"desc": "Franquicia SENCE, OTEC, cursos, precontrato, saldo, capacitación", "tabla": "coach_sence",    "local": None},
}

# ==========================================
# CARGAR RECURSOS
# ==========================================
def cargar_recursos():
    print("📥 Cargando modelo de embeddings local (Hugging Face)...")
    hf_emb = HuggingFaceEmbeddings(model_name=MODELO_EMBEDDINGS) if HuggingFaceEmbeddings else None
    if hf_emb is None:
        print("  ⚠️ langchain-huggingface no instalado: se omiten los índices FAISS locales.")
    recursos = {}
    print("🧠 Despertando Router Híbrido Mente 360...")
    for nombre, cfg in ELEMENTOS.items():
        if cfg.get("local") and hf_emb is not None and FAISS is not None and os.path.exists(cfg["local"]):
            try:
                vs = FAISS.load_local(cfg["local"], hf_emb, allow_dangerous_deserialization=True)
                recursos[nombre] = {"tipo": "faiss", "vs": vs, "tabla": None}
                print(f"  ✅ [LOCAL FAISS] {nombre} conectado ({cfg['local']}).")
            except Exception as e:
                print(f"  ⚠️ {nombre} error FAISS: {e}")
        if cfg.get("tabla"):
            tablas = cfg["tabla"] if isinstance(cfg["tabla"], list) else [cfg["tabla"]]
            recursos[nombre] = {"tipo": "supabase", "vs": None, "tabla": tablas}
            print(f"  ☁️  [SUPABASE] {nombre} vinculado a tabla(s) {', '.join(tablas)}.")
    return recursos

# ==========================================
# ROUTER
# ==========================================
def enrutar(pregunta):
    print("🧭 [1/3 ROUTER] Clasificando pregunta en uno de los 6 Elementos (Agua, Aire, Fuego, Tierra, Metal, Sence)...")
    descripciones = "\n".join([f"- {k}: {v['desc']}" for k, v in ELEMENTOS.items()])
    prompt = f"""Eres el Router de la Mente 360. Tienes 6 elementos:
{descripciones}

Reglas:
- Si la pregunta menciona "SENCE", "franquicia", "OTEC", "capacitación", "saldo SENCE", "precontrato" → Sence.
- Si mezcla temas, devuelve varios separados por coma.
- Responde SOLO con el nombre del elemento (o elementos) separados por coma. Sin texto extra.

Pregunta: {pregunta}
"""
    chain = PromptTemplate(template=prompt, input_variables=[]) | _requerir_llm() | StrOutputParser()
    raw = chain.invoke({}).strip().replace("[", "").replace("]", "")
    elegidos = [e.strip() for e in raw.split(",") if e.strip() in ELEMENTOS]
    if not elegidos:
        elegidos = ["Metal"]  # fallback
    print(f"🎯 Elemento(s) seleccionado(s): {', '.join(elegidos)}")
    return elegidos

# ==========================================
# PROFESOR (asigna coach dentro del elemento)
# ==========================================
def profesor(elemento, pregunta):
    print(f"👨‍🏫 [2/3 PROFESOR {elemento}] Consultando directrices...")
    ruta_md = f"./profesores/{elemento.lower()}.md"
    if os.path.exists(ruta_md):
        with open(ruta_md, "r", encoding="utf-8") as f:
            directrices = f.read()[:2000]
    else:
        directrices = f"Eres el Profesor Supervisor del Elemento {elemento}."
    prompt = f"""{directrices}

Dado que la pregunta es: "{pregunta}"
Asigna al Coach más adecuado de este elemento. Responde SOLO con el nombre del coach (ej: "Coach SENCE", "Coach Contabilidad", "Coach Presupuestos").
"""
    chain = PromptTemplate(template=prompt, input_variables=[]) | _requerir_llm() | StrOutputParser()
    coach = chain.invoke({}).strip()
    print(f"  👨‍🏫 [2/3 PROFESOR {elemento}] Asignó a: {coach}")
    return coach

# ==========================================
# BÚSQUEDA EN EL RECURSO DEL ELEMENTO
# ==========================================
def buscar_contexto(elemento, pregunta, recurso):
    print(f"🔍 [3/3 COACH + RAG] Buscando en {elemento}...")
    if recurso["tipo"] == "faiss":
        docs = recurso["vs"].similarity_search(pregunta, k=3)
        ctx = "\n\n".join([d.page_content for d in docs])
        print(f"  🔎 Búsqueda exitosa en FAISS local ({elemento}).")
        return ctx
    else:
        # Supabase: usar la RPC correcta
        model = SentenceTransformer(MODELO_EMBEDDINGS)
        vector = model.encode(pregunta).tolist()
        ctx_partes = []
        for tabla in recurso["tabla"]:
            try:
                res = supabase.rpc("match_coach_sence", {
                    "query_embedding": vector,
                    "match_threshold": 0.0,
                    "match_count": 3,
                }).execute()
                for r in res.data or []:
                    ctx_partes.append(f"[{tabla}] {r.get('contenido','')}")
                print(f"  🔎 Búsqueda exitosa en Supabase tabla '{tabla}' ({elemento}: {len(res.data or [])} fragmentos).")
            except Exception as e:
                print(f"  ⚠️ Error RPC en '{tabla}': {e}")
        return "\n\n".join(ctx_partes)

# ==========================================
# SÍNTESIS
# ==========================================
def sintetizar(pregunta, contexto, coach, elemento):
    print(f"🤔 Sintetizando respuesta como {coach} (Elemento {elemento})...")
    prompt = f"""Eres {coach} del Elemento {elemento} de DepaFix.
Responde de forma técnica y accionable. Si el contexto no tiene la respuesta, di que no la tienes. NO inventes.

Contexto recuperado:
{contexto}

Pregunta: {pregunta}

Respuesta:
"""
    chain = PromptTemplate(template=prompt, input_variables=[]) | _requerir_llm() | StrOutputParser()
    return chain.invoke({})

# ==========================================
# TOOL: SALDO SENCE POR RUT (mock + búsqueda real)
# ==========================================
def calcular_saldo_sence(rut, trabajadores=None):
    """
    Tool de cálculo de saldo SENCE por RUT.

    Delega en `sence_tools.calcular_saldo_franquicia`:
      - RUT existe en `franquicia_empresas` -> saldo REAL (`es_estimacion: false`).
      - RUT ausente -> estimación 6% de la masa imponible con tope anual
        4,5 UTM por empresa (`es_estimacion: true`).

    Parámetros:
      - rut: RUT de la empresa (ej: "76.123.456-7").
      - trabajadores: lista de dicts con clave 'remuneracion' (CLP). Si es None
        o [], la estimación queda en 0 (no hay masa que imputar).

    Devuelve el JSON completo de sence_tools (sin campos nulos) más los
    alias documentados `saldo_disponible`, `remanente` y `vigencia`.
    """
    from sence_tools import calcular_saldo_franquicia

    saldo = calcular_saldo_franquicia(rut, trabajadores or [])

    # Contexto normativo (RAG coach_sence). No bloquea la tool: si falla, [].
    fragmentos = []
    try:
        model = SentenceTransformer(MODELO_EMBEDDINGS)
        vector = model.encode(f"saldo franquicia SENCE para RUT {rut}").tolist()
        res = supabase.rpc("match_coach_sence", {
            "query_embedding": vector,
            "match_threshold": 0.0,
            "match_count": 3,
        }).execute()
        fragmentos = [r.get("contenido", "")[:200] for r in (res.data or [])]
    except Exception:
        fragmentos = []

    return {
        **saldo,                      # JSON real de sence_tools (sin nulls)
        "saldo_disponible": saldo.get("disponible"),
        "remanente": saldo.get("disponible"),
        "vigencia": saldo.get("año"),
        "contexto_recuperado": fragmentos,
    }

# ==========================================
# MAIN
# ==========================================
def main():
    if not os.getenv("OPENCODE_API_KEY"):
        print("❌ ERROR: Falta OPENCODE_API_KEY en .env")
        return
    if not os.getenv("SUPABASE_URL") or not os.getenv("SUPABASE_SERVICE_ROLE_KEY"):
        print("❌ ERROR: Falta SUPABASE_URL o SUPABASE_SERVICE_ROLE_KEY en .env")
        return

    recursos = cargar_recursos()
    print(f"✅ Recursos listos: {sum(1 for r in recursos.values() if r['tipo']=='faiss')} cerebros FAISS | Supabase: conectado.\n")

    # Modo CLI: pregunta por argumento o interactivo
    if len(sys.argv) > 1:
        preguntas = [" ".join(sys.argv[1:])]
    else:
        preguntas = None

    while True:
        if preguntas:
            pregunta = preguntas.pop(0)
            if not pregunta:
                break
        else:
            try:
                pregunta = input("\n💬 Pregunta (o 'salir'): ")
            except EOFError:
                break
            if pregunta.lower() in ['salir', 'exit', 'quit']:
                break
            if not pregunta.strip():
                continue

        print(f"\n💬 Pregunta: {pregunta}")
        elementos = enrutar(pregunta)

        contexto_total = ""
        for elemento in elementos:
            recurso = recursos.get(elemento)
            if not recurso:
                print(f"  ⚠️ No hay recurso cargado para {elemento}")
                continue
            coach = profesor(elemento, pregunta)
            contexto = buscar_contexto(elemento, pregunta, recurso)
            contexto_total += f"\n[Elemento: {elemento} | Coach: {coach}]\n{contexto}\n"

        if not contexto_total.strip():
            print("\n❌ No se pudo recuperar contexto.")
            continue

        # Elegimos el primer elemento para el system prompt final
        primer_coach = profesor(elementos[0], pregunta) if elementos else "Coach General"
        respuesta = sintetizar(pregunta, contexto_total, primer_coach, elementos[0] if elementos else "General")

        print("\n" + "="*50)
        print(respuesta)
        print("="*50)

        if preguntas is not None and not preguntas:
            break

if __name__ == "__main__":
    # Modo tool: python3 mente_360.py --saldo-sence <RUT> [--masa <CLP>]
    #   --masa <CLP>: masa remuneracional anual en CLP, para que la
    #   estimación (RUT sin registro) sea distinta de 0.
    #   Ej: python3 mente_360.py --saldo-sence 77253931-2 --masa 5000000
    if len(sys.argv) >= 3 and sys.argv[1] == "--saldo-sence":
        rut = sys.argv[2].strip()
        trabajadores = []
        if len(sys.argv) >= 5 and sys.argv[3] == "--masa":
            try:
                trabajadores = [{"remuneracion": float(sys.argv[4])}]
            except ValueError:
                print("ERROR: --masa debe ser un numero en CLP (ej: --masa 5000000)")
                sys.exit(2)
        print(json.dumps(calcular_saldo_sence(rut, trabajadores), ensure_ascii=False, indent=2))
        sys.exit(0)
    main()
