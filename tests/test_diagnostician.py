from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from ceo.diagnostician import (
    ACTION_WHITELIST,
    Diagnosis,
    DiagResult,
    _cache,
    _hash_contexto,
    diagnosticar_fallo,
)


class FakeCompletions:
    def __init__(self, content):
        self.content = content
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content=self.content)
                )
            ]
        )


class FakeOpenAI:
    def __init__(self, content):
        self.completions = FakeCompletions(content)
        self.chat = SimpleNamespace(completions=self.completions)


@pytest.fixture(autouse=True)
def _limpiar_cache():
    _cache.clear()
    yield
    _cache.clear()


def _json_diagnostico(**overrides):
    data = {
        "diagnostico": "feed caído por timeout",
        "accion_sugerida": "health_rerun",
        "target": "depafix-ceo",
        "confianza": 0.9,
        "requiere_humano": False,
    }
    data.update(overrides)
    return json.dumps(data)


def test_diagnostico_valido_con_kimi_y_knowledge_core():
    fake = FakeOpenAI(_json_diagnostico())
    with patch("ceo.diagnostician.MOONSHOT_KEY", "test-key"), \
         patch("ceo.diagnostician.OpenAI", return_value=fake), \
         patch("ceo.diagnostician.diagnosticar_error",
               return_value="Manual: reiniciar el feed"):
        r = diagnosticar_fallo("feed timeout", domain="feed")

    assert isinstance(r, DiagResult)
    assert r.ok is True
    assert r.diagnosis is not None
    assert r.diagnosis.diagnostico == "feed caído por timeout"
    assert r.diagnosis.accion_sugerida == "health_rerun"
    assert r.diagnosis.target == "depafix-ceo"
    assert r.diagnosis.confianza == 0.9
    assert r.diagnosis.requiere_humano is False
    assert r.knowledge_core_usado is True
    assert r.cached is False

    assert len(fake.completions.calls) == 1
    llamada = fake.completions.calls[0]
    assert llamada["temperature"] == 1.0
    prompt = llamada["messages"][1]["content"]
    assert "feed timeout" in prompt
    assert "Manual: reiniciar el feed" in prompt


def test_confianza_baja_sin_conocimiento_requiere_humano():
    fake = FakeOpenAI(_json_diagnostico(
        diagnostico="No hay información suficiente para determinar la causa",
        accion_sugerida="notificar_humano",
        target=None,
        confianza=0.3,
        requiere_humano=True,
    ))
    with patch("ceo.diagnostician.MOONSHOT_KEY", "test-key"), \
         patch("ceo.diagnostician.OpenAI", return_value=fake), \
         patch("ceo.diagnostician.diagnosticar_error", return_value=""):
        r = diagnosticar_fallo("error desconocido")

    assert r.ok is True
    assert r.diagnosis is not None
    assert r.diagnosis.confianza < 0.6
    assert r.diagnosis.requiere_humano is True
    assert r.diagnosis.accion_sugerida == "notificar_humano"


def test_sin_api_key_falla_sin_llamar_openai():
    fake = FakeOpenAI(_json_diagnostico())
    with patch("ceo.diagnostician.MOONSHOT_KEY", None), \
         patch("ceo.diagnostician.OpenAI", return_value=fake), \
         patch("ceo.diagnostician.diagnosticar_error", return_value=""):
        r = diagnosticar_fallo("error")

    assert r.ok is False
    assert "MOONSHOT_API_KEY" in r.motivo
    assert fake.completions.calls == []


def test_json_invalido_devuelve_ok_false():
    fake = FakeOpenAI("esto no es json")
    with patch("ceo.diagnostician.MOONSHOT_KEY", "test-key"), \
         patch("ceo.diagnostician.OpenAI", return_value=fake), \
         patch("ceo.diagnostician.diagnosticar_error", return_value=""):
        r = diagnosticar_fallo("error")

    assert r.ok is False
    assert "JSON" in r.motivo


def test_cache_evita_segunda_llamada_al_llm():
    fake = FakeOpenAI(_json_diagnostico())
    with patch("ceo.diagnostician.MOONSHOT_KEY", "test-key"), \
         patch("ceo.diagnostician.OpenAI", return_value=fake), \
         patch("ceo.diagnostician.diagnosticar_error", return_value="contexto"):
        r1 = diagnosticar_fallo("mismo error")
        r2 = diagnosticar_fallo("mismo error")

    assert r1.ok is True
    assert r2.ok is True
    assert r2.cached is True
    assert len(fake.completions.calls) == 1


def test_whitelist_incluye_ninguna_y_hash_es_sha256():
    assert "ninguna" in ACTION_WHITELIST
    assert len(ACTION_WHITELIST) == 6
    assert _hash_contexto("abc") == _hash_contexto("abc")
    assert len(_hash_contexto("abc")) == 64


def test_schema_rechaza_accion_invalida_y_confianza_fuera_rango():
    with pytest.raises(ValidationError):
        Diagnosis(
            diagnostico="test",
            accion_sugerida="rm_rf",
            confianza=0.5,
        )
    with pytest.raises(ValidationError):
        Diagnosis(
            diagnostico="test",
            accion_sugerida="health_rerun",
            confianza=1.5,
        )
