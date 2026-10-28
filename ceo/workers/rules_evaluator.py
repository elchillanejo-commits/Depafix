"""rules_evaluator.py — Worker que evalúa reglas duras cada 15 min."""
from __future__ import annotations

import json
import logging
import os

from dotenv import load_dotenv
from supabase import create_client

from ceo.rules_engine import evaluar_reglas
from ceo.diagnostician import diagnosticar_fallo
from ceo.predictor import predecir

load_dotenv()
log = logging.getLogger(__name__)


def _construir_error_log(resultado: dict) -> str:
    """Convierte el veredicto de reglas en texto para el diagnóstico."""
    lineas = [f"Veredicto: {resultado.get('veredicto', 'unknown')}"]
    for regla in resultado.get("reglas_disparadas") or []:
        lineas.append(
            f"[{regla.get('regla')}/{regla.get('nivel')}] {regla.get('motivo')}"
        )
    metricas = resultado.get("metricas") or {}
    if metricas:
        lineas.append(
            f"Métricas: {json.dumps(metricas, ensure_ascii=False, default=str)}"
        )
    return "\n".join(lineas)


def rules_evaluator_worker(params: dict | None = None) -> dict:
    """Evalúa reglas duras. Si fail, dispara diagnosticar_fallo (LLM). Fail-open."""
    try:
        client = create_client(
            os.environ["SUPABASE_URL"],
            os.environ["SUPABASE_SERVICE_ROLE_KEY"],
        )
        resultado = evaluar_reglas(client)
        # Inicializar antes del branch (fix UnboundLocalError)
        diagnostico = None
        accion_res = None
        predicciones = []

        # S6: Predecir
        predicciones = predecir(client)

        veredicto = resultado.get("veredicto")

        if veredicto == "fail":
            log.warning("REGLAS FAIL: %s", resultado.get("reglas_disparadas"))
            try:
                diagnostico = diagnosticar_fallo(_construir_error_log(resultado))
                dx = diagnostico.diagnosis
                log.info(
                    "Diagnóstico: ok=%s accion=%s confianza=%s motivo=%s",
                    diagnostico.ok,
                    dx.accion_sugerida if dx else None,
                    dx.confianza if dx else None,
                    diagnostico.motivo,
                )
            except Exception as e:
                log.warning("diagnosticar_fallo falló (fail-open): %s", e)
                diagnostico = None

            # S4: si diagnóstico OK, ejecutar acción sugerida (dry_run por default)
            if diagnostico and diagnostico.ok and diagnostico.diagnosis is not None:
                try:
                    from ceo.actuator import ejecutar_accion
                    accion_res = ejecutar_accion(
                        client,
                        diagnostico,
                        decision_id=None,
                    )
                    log.info(
                        "Acción: %s | resultado=%s",
                        accion_res.get("accion"),
                        accion_res.get("resultado"),
                    )
                except Exception as e:
                    log.warning("actuator falló (fail-open): %s", e)
                    accion_res = {"ok": False, "error": str(e)[:100]}

        return {
            "ok": True,
            **resultado,
            "diagnostico": diagnostico.model_dump() if diagnostico else None,
            "accion": accion_res,
            "predicciones": predicciones,
        }
    except Exception as e:
        log.exception("rules_evaluator falló")
        return {"ok": False, "error": str(e)[:200]}
