import os
import time
import httpx
from typing import List, Optional, Dict
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from openai import AsyncOpenAI
from supabase import create_client

router = APIRouter(prefix="/api/v1", tags=["Orquestador CEO"])

# Clientes (leyendo de variables de entorno)
openai_client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
supabase = create_client(
    os.environ.get("SUPABASE_URL"),
    os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
)

# Caché en memoria con TTL (1 hora)
cache_db: Dict[str, dict] = {}
CACHE_TTL = 3600  # segundos

class PreguntaRequest(BaseModel):
    pregunta: str = Field(..., description="Pregunta del usuario.")
    dominio: Optional[str] = Field(None, description="Dominio opcional: tierra, metal, agua, aire, fuego.")

class RespuestaResponse(BaseModel):
    dominio_detectado: str
    respuesta: str
    fuentes: List[str]
    uf_del_dia: Optional[float] = None
    cache_hit: bool = False

async def obtener_valor_uf() -> Optional[float]:
    """Obtiene el valor actual de la UF desde mindicador.cl."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get("https://mindicador.cl/api/uf")
            if response.status_code == 200:
                data = response.json()
                return float(data["serie"][0]["valor"])
    except Exception:
        pass
    return None

async def clasificar_dominio(pregunta: str) -> str:
    """Usa gpt-4o-mini para clasificar la pregunta en los dominios de DepaFix."""
    prompt = (
        "Clasifica la siguiente pregunta en uno de estos dominios exactos: "
        "'tierra' (obras, presupuestos, construcción, SERVIU), 'metal' (legal, contratos), "
        "'agua' (ecommerce, dropshipping), 'aire' (marketing, ads), 'fuego' (IA, código). "
        "Responde únicamente con el nombre del dominio en minúsculas."
    )
    try:
        response = await openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": prompt}, {"role": "user", "content": pregunta}],
            temperature=0.0,
            max_tokens=10
        )
        dominio = response.choices[0].message.content.strip().lower()
        return dominio if dominio in ["tierra", "metal", "agua", "aire", "fuego"] else "tierra"
    except Exception:
        return "tierra"

async def consultar_rag_supabase(pregunta: str, dominio: str) -> dict:
    """Consulta REAL a Supabase usando pgvector (match_knowledge_v2)."""
    try:
        # 1. Generar embedding de la pregunta
        emb_response = await openai_client.embeddings.create(
            input=pregunta,
            model="text-embedding-3-small",
            dimensions=384
        )
        embedding = emb_response.data[0].embedding

        # 2. Buscar en Supabase
        r = supabase.rpc('match_knowledge_v2', {
            'query_embedding': embedding,
            'filtro_domain': dominio,
            'match_count': 3
        }).execute()

        if not r.data:
            return {"contexto": "No se encontraron chunks relevantes en la base de datos.", "fuentes": []}

        textos = [row.get('content', '') for row in r.data]
        fuentes = list(set([row.get('source_file', 'Desconocido') for row in r.data]))

        return {
            "contexto": "\n\n".join(textos),
            "fuentes": fuentes
        }
    except Exception as e:
        return {"contexto": f"Error en RAG: {str(e)}", "fuentes": []}

@router.post("/preguntar", response_model=RespuestaResponse)
async def orquestador_preguntar(body: PreguntaRequest):
    """Endpoint principal del Orquestador CEO."""
    pregunta_key = body.pregunta.strip().lower()
    ahora = time.time()

    # 1. Verificar caché en memoria (TTL 1 hora)
    if pregunta_key in cache_db:
        cached = cache_db[pregunta_key]
        if ahora - cached["timestamp"] < CACHE_TTL:
            return RespuestaResponse(
                dominio_detectado=cached["dominio"],
                respuesta=cached["respuesta"],
                fuentes=cached["fuentes"],
                uf_del_dia=cached.get("uf_del_dia"),
                cache_hit=True
            )
        else:
            del cache_db[pregunta_key]  # Expirado

    # 2. Determinar dominio
    dominio = body.dominio.lower() if body.dominio else await clasificar_dominio(body.pregunta)

    # 3. Consultar RAG real en Supabase
    rag_data = await consultar_rag_supabase(body.pregunta, dominio)

    # 4. Obtener UF si aplica
    uf_valor = None
    if any(term in body.pregunta.lower() for term in ["uf", "precio", "costo", "cuánto", "presupuesto", "valor"]):
        uf_valor = await obtener_valor_uf()

    # 5. Generar respuesta con OpenAI
    system_prompt = (
        f"Eres el Agente CEO de DepaFix, experto en el dominio '{dominio}'. "
        "Responde la pregunta usando EXCLUSIVAMENTE el siguiente contexto RAG. "
        "Si el valor de la UF es relevante, intégralo en el cálculo. Cita las fuentes al final."
    )
    user_content = f"Pregunta: {body.pregunta}\n\nContexto RAG:\n{rag_data['contexto']}"
    if uf_valor:
        user_content += f"\n\nValor UF actual: ${uf_valor} CLP"

    try:
        completion = await openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            temperature=0.2
        )
        respuesta_texto = completion.choices[0].message.content
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Error OpenAI: {str(e)}")

    resultado = {
        "dominio_detectado": dominio,
        "respuesta": respuesta_texto,
        "fuentes": rag_data["fuentes"],
        "uf_del_dia": uf_valor,
        "cache_hit": False
    }

    # 6. Guardar en caché
    cache_db[pregunta_key] = {
        "dominio": dominio,
        "respuesta": respuesta_texto,
        "fuentes": rag_data["fuentes"],
        "uf_del_dia": uf_valor,
        "timestamp": ahora
    }

    return RespuestaResponse(**resultado)
