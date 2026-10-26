from __future__ import annotations

import json
from types import SimpleNamespace

import openai

from src.agencia import motor_cda
from src.agencia.cda import creatividades
from src.agencia.esquemas import SimulacionRequest
from src.agencia.motor_cda import MotorCDA


def _request() -> SimulacionRequest:
    return SimulacionRequest(presupuesto_pauta_mensual_clp=1_000_000, persistir=False)


def _fake_openai(texto: str):
    llamadas = []
    base_urls = []

    class FakeOpenAI:
        def __init__(self, api_key=None, base_url=None):
            self.api_key = api_key
            base_urls.append(base_url)
            self.chat = SimpleNamespace(
                completions=SimpleNamespace(create=self._create)
            )

        def _create(self, **kwargs):
            llamadas.append(kwargs)
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(message=SimpleNamespace(content=texto))
                ]
            )

    return FakeOpenAI, llamadas, base_urls


def test_creatividades_usan_rag_y_moonshot(monkeypatch):
    monkeypatch.setattr(motor_cda, "USE_MOCK_LLM", False)
    monkeypatch.setenv("MOONSHOT_API_KEY", "test-key")

    consultas = []

    def fake_rag(consulta: str) -> str:
        consultas.append(consulta)
        return "Contexto RAG de prueba"

    monkeypatch.setattr(motor_cda, "obtener_contexto_relevante", fake_rag)
    copys = [
        {
            "titulo": f"Titulo LLM {indice}",
            "cuerpo": f"Cuerpo LLM {indice}",
            "cta": f"CTA LLM {indice}",
        }
        for indice in range(1, 4)
    ]
    FakeOpenAI, llamadas, base_urls = _fake_openai(json.dumps(copys))
    monkeypatch.setattr(openai, "OpenAI", FakeOpenAI)

    resultado = MotorCDA().simular(_request())

    assert len(llamadas) == 2
    assert base_urls == [
        "https://api.moonshot.ai/v1",
        "https://api.moonshot.ai/v1",
    ]
    assert consultas == [
        "anuncios de alta conversión para el rubro salud_genetica en el embudo B2C",
        "anuncios de alta conversión para el rubro salud_genetica en el embudo B2B",
    ]

    for embudo in resultado.embudos:
        assert [item.titulo for item in embudo.creatividades] == [
            "Titulo LLM 1",
            "Titulo LLM 2",
            "Titulo LLM 3",
        ]
        assert [item.formato for item in embudo.creatividades] == [
            item.formato for item in creatividades(embudo.embudo)
        ]

    assert llamadas[0]["model"] == motor_cda.LLM_MODEL
    assert "Contexto RAG de prueba" in llamadas[0]["messages"][0]["content"]


def test_fallback_si_rag_falla(monkeypatch):
    monkeypatch.setattr(motor_cda, "USE_MOCK_LLM", False)
    monkeypatch.setenv("MOONSHOT_API_KEY", "test-key")

    def rag_fallido(_consulta: str) -> str:
        raise RuntimeError("Supabase no disponible")

    monkeypatch.setattr(motor_cda, "obtener_contexto_relevante", rag_fallido)

    def no_llamar(*_args, **_kwargs):
        raise AssertionError("No se debe llamar al LLM si el RAG falló")

    monkeypatch.setattr(openai, "OpenAI", no_llamar)

    resultado = MotorCDA().simular(_request())

    for embudo in resultado.embudos:
        assert embudo.creatividades == creatividades(embudo.embudo)


def test_fallback_si_moonshot_falla(monkeypatch):
    monkeypatch.setattr(motor_cda, "USE_MOCK_LLM", False)
    monkeypatch.setenv("MOONSHOT_API_KEY", "test-key")
    monkeypatch.setattr(
        motor_cda, "obtener_contexto_relevante", lambda _consulta: "Contexto RAG"
    )

    class MoonshotFallido:
        def __init__(self, api_key=None, base_url=None):
            raise RuntimeError("Moonshot no disponible")

    monkeypatch.setattr(openai, "OpenAI", MoonshotFallido)

    resultado = MotorCDA().simular(_request())

    for embudo in resultado.embudos:
        assert embudo.creatividades == creatividades(embudo.embudo)
