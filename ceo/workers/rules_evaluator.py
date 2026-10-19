"""rules_evaluator.py — Worker que evalúa reglas duras cada 15 min."""
from __future__ import annotations

import logging
import os

from dotenv import load_dotenv
from supabase import create_client

from ceo.rules_engine import evaluar_reglas
from ceo.diagnostician import diagnosticar_fallo
from ceo.predictor import predecir

load_dotenv()
log = logging.getLogger(__name__)


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
                diagnostico = diagnosticar_fallo(client, resultado)
                log.info("Diagnóstico: accion=%s confianza=%s costo=$%s",
                         diagnostico.get("accion_sugerida"),
                         diagnostico.get("confianza"),
                         diagnostico.get("costo_usd"))
            except Exception as e:
                log.warning("diagnosticar_fallo falló (fail-open): %s", e)
                diagnostico = {"ok": False, "motivo_skip": f"excepcion: {str(e)[:80]}"}

            # S4: si diagnóstico OK, ejecutar acción sugerida (dry_run por default)
            accion_res = None
            if diagnostico and diagnostico.get("ok"):
                try:
                    from ceo.actuator import ejecutar_accion
                    accion_sug = diagnostico.get("accion_sugerida") or "notificar_humano"
                    target = ""
                    if accion_sug == "task_rerun":
                        target = str(diagnostico.get("decision_id") or "")
                    elif accion_sug == "notificar_humano":
                        target = diagnostico.get("diagnostico") or "fallo detectado"
                    elif accion_sug == "systemctl_restart":
                        target = "depafix-trading"
                    accion_res = ejecutar_accion(
                        client,
                        decision_id=diagnostico.get("decision_id"),
                        accion=accion_sug,
                        target=target,
                        confianza=diagnostico.get("confianza") or 0.0,
                    )
                    log.info("Acción: %s | resultado=%s", accion_sug, accion_res.get("resultado"))
                except Exception as e:
                    log.warning("actuator falló (fail-open): %s", e)
                    accion_res = {"ok": False, "error": str(e)[:100]}

        return {"ok": True, **resultado, "diagnostico": diagnostico, "accion": accion_res, "predicciones": predicciones}
    except Exception as e:
        log.exception("rules_evaluator falló")
        return {"ok": False, "error": str(e)[:200]}
