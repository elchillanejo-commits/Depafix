"""Tests para ceo/predictor.py con FakeClient custom."""
from __future__ import annotations

from ceo.predictor import predecir


class FakeResp:
    def __init__(self, data=None):
        self.data = data or []


class FakeQuery:
    """Simula la chain de postgrest. Ignora filtros y devuelve data fija."""
    def __init__(self, data):
        self._data = data
    def select(self, *a, **k): return self
    def eq(self, *a, **k): return self
    def gte(self, *a, **k): return self
    def order(self, *a, **k): return self
    def limit(self, *a, **k): return self
    def execute(self): return FakeResp(self._data)


class FakeClient:
    """Simula supabase client. Permite definir data por tabla."""
    def __init__(self, health_rows=None, existing_preds=None):
        self._health = health_rows or []
        self._preds = existing_preds or []
    def table(self, name):
        if name == "ceo_predictions":
            return FakeQuery(self._preds)
        return FakeQuery(self._health)


def _row(source, target, status, latency=0, ts="2023-10-06T10:00:00"):
    return {"source": source, "target": target, "status": status,
            "latency_ms": latency, "ts": ts}


def test_fail_recurrente_detectado():
    """12 fails consecutivos → patron fail_recurrente."""
    rows = [_row("s1", "t1", "fail") for _ in range(12)]
    c = FakeClient(health_rows=rows, existing_preds=[])
    preds = predecir(c)
    assert any(p["patron"] == "fail_recurrente" for p in preds), \
        f"esperaba fail_recurrente, obtuve: {preds}"


def test_no_false_positive_flat():
    """12 oks → sin predicciones."""
    rows = [_row("s1", "t1", "ok", latency=160) for _ in range(12)]
    c = FakeClient(health_rows=rows, existing_preds=[])
    preds = predecir(c)
    assert not any(p["patron"] == "fail_recurrente" for p in preds)


def test_fail_open_supabase_error():
    """Si el cliente falla, retorna [] sin excepción."""
    class Broken:
        def table(self, _):
            raise RuntimeError("boom")
    assert predecir(Broken()) == []


def test_hysteresis_no_repite():
    """Si ya hay predicción reciente, no duplica."""
    rows = [_row("s1", "t1", "fail") for _ in range(12)]
    existing = [{"id": 1, "patron": "fail_recurrente", "source": "s1", "target": "t1"}]
    c = FakeClient(health_rows=rows, existing_preds=existing)
    preds = predecir(c)
    # Puede devolver 0 porque ya_emitido detecta el existente
    assert all(p["patron"] != "fail_recurrente" for p in preds)
