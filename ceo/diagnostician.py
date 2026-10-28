"""diagnostician.py — Diagnóstico con Kimi y Knowledge Core cuando veredicto == fail.

Fail-open: si Kimi falla, retorna ok=False sin tocar nada.
Solo se invoca desde rules_evaluator (no como worker independiente).
Caché por contexto_hash (2h) para ahorrar llamadas.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Literal

from openai import OpenAI
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from dotenv import load_dotenv

# Importamos nuestro Knowledge Core
from knowledge.diagnostician import diagnosticar_error

load_dotenv()
log = logging.getLogger(__name__)

# Configuración de Kimi
MOONSHOT_KEY = os.environ.get("MOONSHOT_API_KEY") or os.environ.get("OPENAI_API_KEY")
MODEL_NAME = os.environ.get("LLM_MODEL", "kimi-k3.1-pro")
MAX_TOKENS = 800
TIMEOUT_S = 30
CACHE_HORAS = 2

ACTION_WHITELIST = {
    "systemctl_restart", "task_rerun", "bot_pausar",
    "notificar_humano", "health_rerun", "ninguna"
}

class Diagnosis(BaseModel):
    """Modelo estructurado de salida del LLM (Pydantic v2)."""
    model_config = ConfigDict(extra="forbid")

    diagnostico: str = Field(description="Causa probable del fallo en 1-2 oraciones.")
    accion_sugerida: Literal[
        "systemctl_restart", "task_rerun", "bot_pausar",
        "notificar_humano", "health_rerun", "ninguna"
    ]
    target: str | None = Field(default=None, description="Target del servicio o task, si aplica.")
    confianza: float = Field(ge=0.0, le=1.0)
    requiere_humano: bool = Field(default=False)

class DiagResult(BaseModel):
    ok: bool
    motivo: str
    diagnosis: Diagnosis | None = None
    cached: bool = False
    knowledge_core_usado: bool = False

# Caché en memoria (se borra al reiniciar el worker)
_cache: dict[str, tuple[datetime, DiagResult]] = {}

def _hash_contexto(prompt: str) -> str:
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()

def _revisar_cache(ctx_hash: str) -> DiagResult | None:
    if ctx_hash in _cache:
        ts, res = _cache[ctx_hash]
        if datetime.now(timezone.utc) - ts < timedelta(hours=CACHE_HORAS):
            return res
        else:
            del _cache[ctx_hash]
    return None

def _guardar_cache(ctx_hash: str, res: DiagResult):
    _cache[ctx_hash] = (datetime.now(timezone.utc), res)

def _construir_prompt(error_log: str, contexto_previo: str) -> str:
    return f"""
    Eres un Ingeniero de Sistemas experto en DepaFix. Analiza el siguiente error y sugiere una acción.
    
    Error actual:
    {error_log}
    
    Contexto técnico previo (extraído de nuestros manuales):
    {contexto_previo}
    
    Reglas ESTRICTAS:
    1. Solo puedes sugerir acciones de esta lista: {', '.join(ACTION_WHITELIST)}.
    2. Si la confianza es menor a 0.6, sugiere 'notificar_humano'.
    3. Devuelve ÚNICAMENTE un objeto JSON válido, sin texto adicional, sin bloques markdown.
    
    El JSON debe tener exactamente esta estructura:
    {{
        "diagnostico": "texto de la causa",
        "accion_sugerida": "una_de_las_acciones_de_la_lista",
        "target": "nombre_del_servicio_o_null",
        "confianza": 0.9,
        "requiere_humano": false
    }}
    """

def diagnosticar_fallo(
    error_log: str, 
    domain: str | None = None
) -> DiagResult:
    """
    Diagnostica un fallo usando Knowledge Core y Kimi.
    """
    # 1. Consultar Knowledge Core primero
    log.info("Consultando Knowledge Core para el error...")
    conocimiento_previo = "No hay contexto disponible de los manuales."
    try:
        conocimiento_previo = diagnosticar_error(error_log, domain=domain)
    except Exception as e:
        log.warning("Falló el Knowledge Core (fail-open): %s", e)

    # 2. Preparar el prompt y revisar caché
    prompt = _construir_prompt(error_log, conocimiento_previo)
    ctx_hash = _hash_contexto(prompt)

    cached_res = _revisar_cache(ctx_hash)
    if cached_res:
        cached_res.cached = True
        return cached_res

    # 3. Verificar API Key
    if not MOONSHOT_KEY:
        return DiagResult(ok=False, motivo="Falta MOONSHOT_API_KEY en el .env")

    # 4. Llamar a Kimi
    llm = OpenAI(api_key=MOONSHOT_KEY, base_url="https://api.moonshot.ai/v1")
    
    try:
        response = llm.chat.completions.create(
            model=MODEL_NAME,
            max_tokens=MAX_TOKENS,
            # KIMI SOLO ACEPTA temperature=1.0
            temperature=1.0,
            messages=[
                {"role": "system", "content": "Eres un SRE experto. Devuelve SOLO JSON válido sin formato markdown."},
                {"role": "user", "content": prompt}
            ],
            timeout=TIMEOUT_S
        )
        
        content = response.choices[0].message.content.strip()
        
        # 5. Parsear el JSON
        try:
            # Limpieza por si Kimi encierra el JSON en markdown
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].strip()

            data = json.loads(content)
            diagnosis = Diagnosis(**data)
            
        except (json.JSONDecodeError, ValidationError) as e:
            log.error("Error parseando JSON del LLM: %s. Texto original: %s", e, content)
            return DiagResult(ok=False, motivo="El LLM no devolvió un JSON válido.")

        # 6. Retornar y guardar en caché
        res = DiagResult(
            ok=True, 
            motivo="Diagnóstico exitoso", 
            diagnosis=diagnosis, 
            knowledge_core_usado=True
        )
        _guardar_cache(ctx_hash, res)
        return res

    except Exception as e:
        log.error("Error en llamada a Kimi: %s", e)
        return DiagResult(ok=False, motivo=f"Error de API Kimi: {e}")
