from __future__ import annotations

from unittest.mock import patch

from ceo.sensors.railway_probe import probe_railway
from ceo.sensors.supabase_probe import probe_supabase
from ceo.sensors.feeds_probe import probe_feeds


class FakeResp:
    def __init__(self, data=None, count=None):
        self.data = data or []
        self.count = count


class FakeClient:
    def __init__(self, counts=None):
        self._counts = counts or {}
    def table(self, name):
        self._current = name
        return self
    def select(self, *a, **k):
        return self
    def limit(self, n):
        return self
    def execute(self):
        return FakeResp(count=self._counts.get(self._current, 0))
    def insert(self, d):
        return self
    def eq(self, *a):
        return self
    def order(self, *a, **k):
        return self


def test_supabase_probe_ok():
    client = FakeClient(counts={
        "velas_cripto": 673,
        "operaciones_ejecutadas": 283,
        "ceo_tasks": 45,
    })
    r = probe_supabase(client)
    assert r["status"] == "ok"
    assert r["filas"]["velas_cripto"] == 673


def test_feeds_probe_fail_en_timeout():
    with patch("ceo.sensors.feeds_probe.requests.get",
               side_effect=Exception("boom")):
        r = probe_feeds(FakeClient())
    assert r["status"] == "fail"
    assert "boom" in str(r.get("error", ""))


def test_feeds_probe_ok():
    class R:
        status_code = 200
    with patch("ceo.sensors.feeds_probe.requests.get", return_value=R()):
        r = probe_feeds(FakeClient())
    assert r["status"] == "ok"
    assert r["health_code"] == 200


def test_railway_probe_sin_cli():
    with patch("ceo.sensors.railway_probe._cli_disponible", return_value=False):
        r = probe_railway(FakeClient())
    assert r["status"] == "skip"


def test_railway_probe_timeout():
    import subprocess
    with patch("ceo.sensors.railway_probe._cli_disponible", return_value=True), \
         patch("ceo.sensors.railway_probe.subprocess.run",
               side_effect=subprocess.TimeoutExpired(cmd="railway", timeout=1)):
        r = probe_railway(FakeClient())
    assert r["status"] == "warn"


def test_railway_probe_ok():
    class R:
        returncode = 0
        stdout = "● Online\n● Online\n"
        stderr = ""
    with patch("ceo.sensors.railway_probe._cli_disponible", return_value=True), \
         patch("ceo.sensors.railway_probe.subprocess.run", return_value=R()):
        r = probe_railway(FakeClient())
    assert r["status"] == "ok"
    assert r["online"] == 2
