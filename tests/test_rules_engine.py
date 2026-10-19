from __future__ import annotations

from datetime import datetime, timedelta, timezone

from ceo.rules_engine import evaluar_reglas


class FakeResp:
    def __init__(self, data=None, count=None):
        self.data = data or []
        self.count = count


def _row(source, target, status, latency=100, min_ago=5, payload=None):
    ts = (datetime.now(timezone.utc) - timedelta(minutes=min_ago)).isoformat()
    return {"source": source, "target": target, "status": status,
            "latency_ms": latency, "ts": ts, "payload": payload or {}}


class FakeClient:
    def __init__(self, rows, count_tasks=0):
        self._rows = rows
        self._count_tasks = count_tasks
        self._mode = None
    def table(self, name):
        self._mode = name
        return self
    def select(self, *a, **k): return self
    def gte(self, *a, **k): return self
    def lte(self, *a, **k): return self
    def eq(self, *a, **k): return self
    def order(self, *a, **k): return self
    @property
    def not_(self): return self
    def like(self, *a, **k): return self
    def is_(self, *a, **k): return self
    def execute(self):
        if self._mode == "ceo_tasks":
            return FakeResp(count=self._count_tasks)
        return FakeResp(data=self._rows)


def test_todo_ok():
    rows = [
        _row("supabase", "core", "ok", 300, 2, {"filas": {"velas_cripto": 500}}),
        _row("supabase", "core", "ok", 350, 17),
        _row("supabase", "core", "ok", 400, 32),
        _row("feed", "depafix-ceo", "ok", 500, 3),
        _row("feed", "depafix-ceo", "ok", 600, 18),
        _row("railway", "services", "ok", None, 4, {"offline": 0}),
    ]
    r = evaluar_reglas(FakeClient(rows))
    assert r["veredicto"] == "ok"
    assert r["reglas_disparadas"] == []


def test_r1_railway_fail_2_ciclos():
    rows = [
        _row("railway", "services", "fail", None, 2),
        _row("railway", "services", "fail", None, 17),
        _row("supabase", "core", "ok", 300, 2, {"filas": {"velas_cripto": 500}}),
    ]
    r = evaluar_reglas(FakeClient(rows))
    assert r["veredicto"] == "fail"
    assert any(d["regla"] == "R1" for d in r["reglas_disparadas"])


def test_r2_supabase_latencia_warn():
    rows = [
        _row("supabase", "core", "ok", 3000, 2, {"filas": {"velas_cripto": 500}}),
        _row("supabase", "core", "ok", 3100, 17),
        _row("supabase", "core", "ok", 3200, 32),
    ]
    r = evaluar_reglas(FakeClient(rows))
    assert any(d["regla"] == "R2" for d in r["reglas_disparadas"])
    # solo 1 warn -> veredicto ok
    assert r["veredicto"] == "ok"


def test_r3_feed_fail_2_ciclos():
    rows = [
        _row("feed", "depafix-ceo", "fail", None, 2),
        _row("feed", "depafix-ceo", "fail", None, 17),
    ]
    r = evaluar_reglas(FakeClient(rows))
    assert r["veredicto"] == "fail"
    assert any(d["regla"] == "R3" for d in r["reglas_disparadas"])


def test_r7_ceo_tasks_vencidas():
    rows = [_row("supabase", "core", "ok", 300, 2, {"filas": {"velas_cripto": 500}})]
    r = evaluar_reglas(FakeClient(rows, count_tasks=200))
    assert any(d["regla"] == "R7" for d in r["reglas_disparadas"])


def test_fail_open_supabase_error():
    class Broken:
        def table(self, _):
            raise RuntimeError("supabase down")
    r = evaluar_reglas(Broken())
    assert r["veredicto"] == "unknown"
    assert "error" in r


def test_multiples_warns_suman():
    rows = [
        _row("supabase", "core", "ok", 3000, 2, {"filas": {"velas_cripto": 50}}),
        _row("supabase", "core", "ok", 3100, 17),
        _row("supabase", "core", "ok", 3200, 32),
        _row("feed", "depafix-ceo", "ok", 12000, 2),
        _row("feed", "depafix-ceo", "ok", 13000, 17),
    ]
    r = evaluar_reglas(FakeClient(rows, count_tasks=200))
    warns = [d for d in r["reglas_disparadas"] if d["nivel"] == "warn"]
    assert len(warns) >= 3
    assert r["veredicto"] == "warn"


def test_source_demo_like_no_silenciado():
    """Bug del `_` wildcard: demostracion_feed NO debe filtrarse."""
    from ceo.rules_engine import _fetch_health

    class FakeResp:
        def __init__(self, data): self.data = data

    class FakeClient:
        def table(self, _): return self
        def select(self, *a, **k): return self
        def gte(self, *a, **k): return self
        def order(self, *a, **k): return self
        def execute(self):
            return FakeResp([
                {"source": "demo_inventario",  "target": "x", "status": "fail",
                 "latency_ms": 100, "ts": "2026-10-07T10:00:00+00:00", "payload": {}},
                {"source": "demostracion_feed", "target": "y", "status": "fail",
                 "latency_ms": 100, "ts": "2026-10-07T10:00:00+00:00", "payload": {}},
                {"source": "feed_cripto",      "target": "z", "status": "fail",
                 "latency_ms": 100, "ts": "2026-10-07T10:00:00+00:00", "payload": {}},
            ])

    rows = _fetch_health(FakeClient())
    sources = {r["source"] for r in rows}
    assert "demo_inventario" not in sources       # filtrado
    assert "demostracion_feed" in sources          # NO filtrado
    assert "feed_cripto" in sources                # NO filtrado
