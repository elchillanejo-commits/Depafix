from __future__ import annotations

from unittest.mock import MagicMock, patch

from ceo.diagnostician import (
    ACTION_WHITELIST,
    _elegir_modelo,
    _hash_contexto,
    diagnosticar_fallo,
)


class FakeResp:
    def __init__(self, data=None, count=None):
        self.data = data or []
        self.count = count


class FakeTable:
    def __init__(self, parent, name):
        self.parent = parent
        self.name = name
        self._filtros = {}
        self._last_data = None
    def select(self, *a, **k): return self
    def insert(self, d): self._last_data = d; return self
    def update(self, d): self._last_data = d; return self
    def eq(self, k, v): self._filtros[k] = v; return self
    def gte(self, *a): return self
    def order(self, *a, **k): return self
    def limit(self, *a): return self
    def execute(self):
        if self.name == "ceo_llm_budget":
            return FakeResp(self.parent.budget_rows)
        if self.name == "ceo_decisions":
            if self._last_data is not None:
                return FakeResp([{"id": 42}])
            return FakeResp(self.parent.decision_rows)
        if self.name == "ceo_health":
            return FakeResp([])
        return FakeResp([])


class FakeClient:
    def __init__(self, budget_rows=None, decision_rows=None):
        self.budget_rows = budget_rows or []
        self.decision_rows = decision_rows or []
    def table(self, name): return FakeTable(self, name)


def _veredicto(reglas=None, nivel="fail"):
    reglas = reglas or [{"regla": "R1", "nivel": nivel, "motivo": "test"}]
    return {"veredicto": "fail", "reglas_disparadas": reglas, "metricas": {}}


def test_skip_veredicto_no_fail():
    r = diagnosticar_fallo(FakeClient(), {"veredicto": "ok", "reglas_disparadas": []})
    assert r["ok"] is False
    assert r["motivo_skip"] == "veredicto_no_fail"


def test_skip_por_presupuesto_dia():
    c = FakeClient(budget_rows=[{"calls_this_hour": 1, "cost_today_usd": 3.0,
                                  "max_calls_per_hour": 5, "max_cost_per_day": 2.0}])
    r = diagnosticar_fallo(c, _veredicto())
    assert r["ok"] is False
    assert r["motivo_skip"] == "presupuesto_dia_agotado"


def test_skip_por_calls_hora():
    c = FakeClient(budget_rows=[{"calls_this_hour": 5, "cost_today_usd": 0.5,
                                  "max_calls_per_hour": 5, "max_cost_per_day": 2.0}])
    r = diagnosticar_fallo(c, _veredicto())
    assert r["ok"] is False
    assert r["motivo_skip"] == "calls_hora_agotadas"


def test_reuso_por_hash():
    c = FakeClient(
        budget_rows=[{"calls_this_hour": 0, "cost_today_usd": 0.0,
                      "max_calls_per_hour": 5, "max_cost_per_day": 2.0}],
        decision_rows=[{"id": 99, "diagnostico": "prev", "accion_sugerida": "task_rerun",
                        "confianza": 0.7, "modelo": "claude-3-5-haiku-latest"}],
    )
    r = diagnosticar_fallo(c, _veredicto())
    assert r["ok"] is True
    assert r["reusada"] is True
    assert r["decision_id"] == 99


def test_fail_open_anthropic_error():
    c = FakeClient(budget_rows=[{"calls_this_hour": 0, "cost_today_usd": 0.0,
                                  "max_calls_per_hour": 5, "max_cost_per_day": 2.0}])
    with patch("ceo.diagnostician.Anthropic") as MockA:
        MockA.side_effect = RuntimeError("anthropic down")
        r = diagnosticar_fallo(c, _veredicto())
    assert r["ok"] is False
    assert "anthropic_error" in r["motivo_skip"]


def test_whitelist_limpia():
    # Verificar que la whitelist tiene 5 items
    assert len(ACTION_WHITELIST) == 5


def test_hash_deterministico():
    v = _veredicto([{"regla": "R1", "nivel": "fail", "motivo": "x"}])
    h1 = _hash_contexto(v)
    h2 = _hash_contexto(v)
    assert h1 == h2
    assert len(h1) == 16


def test_modelo_por_severidad():
    simple = _veredicto([{"regla": "R1", "nivel": "fail", "motivo": "x"}])
    complejo = _veredicto([
        {"regla": "R1", "nivel": "fail", "motivo": "x"},
        {"regla": "R3", "nivel": "fail", "motivo": "y"},
    ])
    assert "haiku" in _elegir_modelo(simple)
    assert "sonnet" in _elegir_modelo(complejo)


def test_schema_rechaza_accion_invalida():
    """Si el LLM devuelve acción fuera del Literal, debe fallback a notificar_humano."""
    from ceo.diagnostician import AccionDiagnostico
    from pydantic import ValidationError

    try:
        AccionDiagnostico(
            diagnostico="test valido de longitud",
            accion_sugerida="rm_rf",  # NO está en el Literal
            confianza=0.5,
        )
        assert False, "Debería haber fallado"
    except ValidationError:
        pass  # correcto


def test_schema_rechaza_confianza_fuera_rango():
    from ceo.diagnostician import AccionDiagnostico
    from pydantic import ValidationError

    try:
        AccionDiagnostico(
            diagnostico="test valido de longitud",
            accion_sugerida="notificar_humano",
            confianza=1.5,  # > 1.0
        )
        assert False, "Debería haber fallado"
    except ValidationError:
        pass


def test_schema_valido_ok():
    from ceo.diagnostician import AccionDiagnostico
    a = AccionDiagnostico(
        diagnostico="feed caido por timeout",
        causa_probable="servicio saturado",
        accion_sugerida="health_rerun",
        confianza=0.7,
        requiere_humano=False,
    )
    assert a.accion_sugerida == "health_rerun"
    assert a.confianza == 0.7
