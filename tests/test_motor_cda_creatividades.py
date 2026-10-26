from __future__ import annotations

import json
import logging
from types import SimpleNamespace

import httpx
import openai

from src.agencia import motor_cda
from src.agencia.cda import creatividades
from src.agencia.esquemas import SimulacionRequest
from src.agencia.motor_cda import MotorCDA


def _request() -> SimulacionRequest:
    return SimulacionRequest(presupuesto_pauta_mensual_clp=1_000_000, persistir=False)


def _fake_openai(texto):
    llamadas = []
    base_urls = []
    respuestas = list(texto) if isinstance(texto, list) else [texto]
    indice = 0

    class FakeOpenAI:
        def __init__(
            self,
            api_key=None,
            base_url=None,
            max_retries=None,
            timeout=None,
        ):
            self.api_key = api_key
            base_urls.append(base_url)
            self.chat = SimpleNamespace(
                completions=SimpleNamespace(create=self._create)
            )

        def _create(self, **kwargs):
            nonlocal indice
            llamadas.append(kwargs)
            respuesta = respuestas[min(indice, len(respuestas) - 1)]
            indice += 1
            if isinstance(respuesta, Exception):
                raise respuesta
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(content=respuesta),
                        finish_reason="stop",
                    )
                ]
            )

    return FakeOpenAI, llamadas, base_urls


def _error_429() -> openai.RateLimitError:
    peticion = httpx.Request(
        "POST", "https://api.moonshot.ai/v1/chat/completions"
    )
    respuesta = httpx.Response(
        429, request=peticion, headers={"retry-after": "0"}
    )
    return openai.RateLimitError(
        "max organization concurrency: 1", response=respuesta, body=None
    )


def _simular_con_texto(monkeypatch, texto):
    monkeypatch.setattr(motor_cda, "USE_MOCK_LLM", False)
    monkeypatch.setenv("MOONSHOT_API_KEY", "test-key")
    monkeypatch.setattr(
        motor_cda, "obtener_contexto_relevante", lambda _consulta: "Contexto RAG"
    )
    monkeypatch.setattr(motor_cda.time, "sleep", lambda _segundos: None)
    FakeOpenAI, llamadas, _ = _fake_openai(texto)
    monkeypatch.setattr(openai, "OpenAI", FakeOpenAI)
    return MotorCDA().simular(_request()), llamadas


def _copys_llm() -> list[dict]:
    return [
        {
            "titulo": f"Titulo LLM {indice}",
            "cuerpo": f"Cuerpo LLM {indice}",
            "cta": f"CTA LLM {indice}",
        }
        for indice in range(1, 4)
    ]


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


def test_parsea_json_con_markdown_y_texto_extra(monkeypatch):
    copys = _copys_llm()
    texto = (
        "Aquí tienes [3 anuncios]:\n```json\n"
        + json.dumps(copys, ensure_ascii=False)
        + "\n```\nEspero que sirvan."
    )

    resultado, llamadas = _simular_con_texto(monkeypatch, texto)

    assert len(llamadas) == 2
    assert [
        item.titulo for item in resultado.embudos[0].creatividades
    ] == [copia["titulo"] for copia in copys]


def test_parsea_json_objeto_con_lista(monkeypatch):
    copys = _copys_llm()
    texto = '{"anuncios": ' + json.dumps(copys, ensure_ascii=False) + "}"

    resultado, _ = _simular_con_texto(monkeypatch, texto)

    assert [
        item.titulo for item in resultado.embudos[0].creatividades
    ] == [copia["titulo"] for copia in copys]


def test_loguea_respuesta_cruda_si_json_falla(monkeypatch, caplog):
    caplog.set_level(logging.ERROR)
    texto = "Lo siento, no puedo generar JSON en este momento."

    resultado, _ = _simular_con_texto(monkeypatch, texto)

    assert texto in caplog.text
    for embudo in resultado.embudos:
        assert embudo.creatividades == creatividades(embudo.embudo)


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
        def __init__(self, api_key=None, base_url=None, **kwargs):
            raise RuntimeError("Moonshot no disponible")

    monkeypatch.setattr(openai, "OpenAI", MoonshotFallido)

    resultado = MotorCDA().simular(_request())

    for embudo in resultado.embudos:
        assert embudo.creatividades == creatividades(embudo.embudo)


def test_reintenta_429_y_luego_genera_copys(monkeypatch):
    copys = _copys_llm()

    resultado, llamadas = _simular_con_texto(
        monkeypatch,
        [_error_429(), json.dumps(copys), json.dumps(copys)],
    )

    assert len(llamadas) == 3
    assert [
        item.titulo for item in resultado.embudos[0].creatividades
    ] == [copia["titulo"] for copia in copys]
    assert [
        item.titulo for item in resultado.embudos[1].creatividades
    ] == [copia["titulo"] for copia in copys]


def test_reintenta_respuesta_vacia(monkeypatch):
    copys = _copys_llm()

    resultado, llamadas = _simular_con_texto(
        monkeypatch,
        ["", json.dumps(copys), json.dumps(copys)],
    )

    assert len(llamadas) == 3
    assert [
        item.titulo for item in resultado.embudos[0].creatividades
    ] == [copia["titulo"] for copia in copys]


def test_fallback_si_respuestas_vacias_persisten(monkeypatch, caplog):
    caplog.set_level(logging.WARNING)

    resultado, llamadas = _simular_con_texto(monkeypatch, "")

    assert len(llamadas) == motor_cda.LLM_MAX_INTENTOS * 2
    assert "respuesta vacía" in caplog.text
    for embudo in resultado.embudos:
        assert embudo.creatividades == creatividades(embudo.embudo)


def test_fallback_si_429_persiste(monkeypatch):
    resultado, llamadas = _simular_con_texto(monkeypatch, [_error_429()])

    assert len(llamadas) == motor_cda.LLM_MAX_INTENTOS * 2
    for embudo in resultado.embudos:
        assert embudo.creatividades == creatividades(embudo.embudo)
