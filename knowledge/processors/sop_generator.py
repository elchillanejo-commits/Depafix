#!/usr/bin/env python3
from __future__ import annotations
import logging
import os
import time
from typing import Any
from openai import OpenAI
from supabase import Client, create_client
from dotenv import load_dotenv

# Cargar variables del .env
load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
LOGGER = logging.getLogger(__name__)

MAX_CHUNKS_PER_RUN = 2
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
MOONSHOT_KEY = os.environ.get("MOONSHOT_API_KEY") or os.environ.get("OPENAI_API_KEY")
MODEL_NAME = os.environ.get("LLM_MODEL", "kimi-k3.1-pro")

def init_clients() -> tuple[Client, OpenAI]:
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise ValueError("Faltan SUPABASE_URL o SUPABASE_SERVICE_ROLE_KEY en el .env")
    if not MOONSHOT_KEY:
        raise ValueError("Falta MOONSHOT_API_KEY o OPENAI_API_KEY en el .env")
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    llm = OpenAI(api_key=MOONSHOT_KEY, base_url="https://api.moonshot.ai/v1")
    return supabase, llm

def _generate_sop(llm: OpenAI, model: str, chunk: dict[str, Any]) -> str:
    prompt = f"Basado en el siguiente texto de un curso de marketing, genera un Procedimiento Operativo Estándar (SOP) paso a paso. Debe ser claro, accionable y tener un máximo de 300 palabras.\n\nTexto original:\n{chunk['content']}"
    for intento in range(1, 4):
        try:
            response = llm.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "Eres un experto en operaciones y marketing digital. Generas SOPs estructurados."},
                    {"role": "user", "content": prompt}
                ],
                temperature=1.0,
                max_tokens=1000
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            LOGGER.warning(f"Error generando SOP (intento {intento}/3): {e}. Reintentando...")
            time.sleep(2 * intento)
    raise RuntimeError(f"No se pudo generar el SOP para el chunk {chunk['id']} tras 3 intentos.")

def main() -> int:
    LOGGER.info("Inicio de generación de SOPs. Límite duro: %d chunks por ejecución.", MAX_CHUNKS_PER_RUN)
    try:
        supabase, llm = init_clients()
    except ValueError as e:
        LOGGER.error("Configuración incompleta: %s", e)
        return 2
    try:
        chunks_resp = supabase.table("knowledge_chunks_v2").select("*").eq("domain", "marketing").execute()
        all_chunks = chunks_resp.data
    except Exception as e:
        LOGGER.error("Error leyendo chunks: %s", e)
        return 1
    if not all_chunks:
        LOGGER.info("No hay chunks de marketing para procesar.")
        return 0
    try:
        derivs_resp = supabase.table("knowledge_derivatives").select("chunk_id").eq("type", "sop").execute()
        existing_sops = {d["chunk_id"] for d in derivs_resp.data}
    except Exception as e:
        LOGGER.error("Error leyendo derivados: %s", e)
        return 1
    pending_chunks = [c for c in all_chunks if c["id"] not in existing_sops]
    if not pending_chunks:
        LOGGER.info("Todos los chunks de marketing ya tienen un SOP generado.")
        return 0
    to_process = pending_chunks[:MAX_CHUNKS_PER_RUN]
    generated = 0
    failed = 0
    for chunk in to_process:
        chunk_id = chunk["id"]
        LOGGER.info("Generando SOP para el chunk %s (%s)...", chunk_id, chunk.get("source_file", "desconocido"))
        try:
            sop_content = _generate_sop(llm, MODEL_NAME, chunk)
            supabase.table("knowledge_derivatives").insert({
                "chunk_id": chunk_id,
                "type": "sop",
                "content": sop_content,
                "generated_by": "sop_generator_v1"
            }).execute()
            generated += 1
            LOGGER.info("SOP guardado para el chunk %s (%d palabras).", chunk_id, len(sop_content.split()))
        except Exception as e:
            LOGGER.error("Error procesando el chunk %s: %s", chunk_id, e)
            failed += 1
    LOGGER.info("Resumen: generados=%d, errores=%d.", generated, failed)
    return 0 if failed == 0 else 1

if __name__ == "__main__":
    raise SystemExit(main())
