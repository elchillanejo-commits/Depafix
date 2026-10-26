from __future__ import annotations

import json
from types import SimpleNamespace

import anthropic

from src.agencia import motor_cda
from src.agencia.cda import creatividades
from src.agencia.esquemas import SimulacionRequest
from src.agencia.motor_cda import MotorCDA


def _request() -> SimulacionRequest:
    return SimulacionRequest(presupuesto_pauta_mensual_clp=1_000_000, persistir=False)


def _fake_anthropic(texto: str):
    llamadas = []

    class FakeAnthropic:
        def __init__(self, api_key=None):
            self.api_key = api_key
            self.messages = SimpleNamespace(create=self._create)

        def _create(self, **kwargs):
            llamadas.append(kwargs)
            return SimpleNamespace(
                content=[SimpleNamespace(type="text", text=texto)]
            )

    return FakeAnthropic, llamadas


def test_creatividades_usan_rag_y_llm(monkeypatch):
    monkeypatch.setattr(motor_cda, "USE_MOCK_LLM", False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

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
    FakeAnthropic, llamadas = _fake_anthropic(json.dumps(copys))
    monkeypatch.setattr(anthropic, "Anthropic", FakeAnthropic)

    resultado = MotorCDA().simular(_request())

    assert len(llamadas) == 2
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

    assert "Contexto RAG de prueba" in llamadas[0]["system"]


def test_fallback_si_rag_falla(monkeypatch):
    monkeypatch.setattr(motor_cda, "USE_MOCK_LLM", False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    def rag_fallido(_consulta: str) -> str:
        raise RuntimeError("Supabase no disponible")

    monkeypatch.setattr(motor_cda, "obtener_contexto_relevante", rag_fallido)

    def no_llamar(*_args, **_kwargs):
        raise AssertionError("No se debe llamar al LLM si el RAG falló")

    monkeypatch.setattr(anthropic, "Anthropic", no_llamar)

    resultado = MotorCDA().simular(_request())

    for embudo in resultado.embudos:
        assert embudo.creatividades == creatividades(embudo.embudo)


def test_fallback_si_llm_falla(monkeypatch):
    monkeypatch.setattr(motor_cda, "USE_MOCK_LLM", False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(
        motor_cda, "obtener_contexto_relevante", lambda _consulta: "Contexto RAG"
    )

    class AnthropicFallido:
        def __init__(self, api_key=None):
            raise RuntimeError("Anthropic no disponible")

    monkeypatch.setattr(anthropic, "Anthropic", AnthropicFallido)

    resultado = MotorCDA().simular(_request())

    for embudo in resultado.embudos:
        assert embudo.creatividades == creatividades(embudo.embudo)
