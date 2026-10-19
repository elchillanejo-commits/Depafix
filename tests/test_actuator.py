from __future__ import annotations

from unittest.mock import patch

from ceo.actuator import ejecutar_accion


class FakeResp:
    def __init__(self, data=None, count=None):
        self.data = data if data is not None else []
        self.count = count


class FakeClient:
    def __init__(self, count_actions=0):
        self._count = count_actions
        self._name = None
        self._last_insert = None
        self._next_id = 100
    def table(self, name):
        self._name = name
        return self
    def select(self, *a, **k):
        return self
    def insert(self, d):
        self._last_insert = d
        self._next_id += 1
        return self
    def update(self, d):
        self._last_insert = d
        return self
    def eq(self, *a, **k):
        return self
    def gte(self, *a, **k):
        return self
    def execute(self):
        if self._name == "ceo_actions":
            # Insert: devolver fila con id. Select count: devolver count.
            if self._last_insert is not None and "accion" in self._last_insert:
                rid = self._next_id
                self._last_insert = None  # reset para próximo insert
                return FakeResp(data=[{"id": rid}])
            return FakeResp(count=self._count)
        return FakeResp()


def test_dry_run_no_ejecuta():
    c = FakeClient()
    with patch("ceo.actuator._actuator_enabled", return_value=False):
        r = ejecutar_accion(c, 1, "task_rerun", "42")
    assert r["resultado"] == "dry_run"


def test_accion_fuera_whitelist():
    c = FakeClient()
    r = ejecutar_accion(c, 1, "rm_rf_slash", "/")
    assert r["resultado"] == "rechazada_whitelist"
    assert r["ok"] is False


def test_target_con_caracteres_invalidos():
    c = FakeClient()
    r = ejecutar_accion(c, 1, "task_rerun", "42; rm -rf ~")
    assert r["resultado"] == "target_invalido"
    assert r["ok"] is False


def test_hysteresis_restart():
    c = FakeClient(count_actions=2)  # ya hay 2 restarts hoy
    with patch("ceo.actuator._actuator_enabled", return_value=True):
        r = ejecutar_accion(c, 1, "systemctl_restart", "depafix-trading")
    assert r["resultado"] == "skip_hysteresis"


def test_task_rerun_ok():
    c = FakeClient()
    with patch("ceo.actuator._actuator_enabled", return_value=True):
        r = ejecutar_accion(c, 1, "task_rerun", "42", dry_run=False)
    assert r["resultado"] == "ok"
    assert r["ok"] is True


def test_bot_pausar_ok():
    c = FakeClient()
    with patch("ceo.actuator._actuator_enabled", return_value=True):
        r = ejecutar_accion(c, 1, "bot_pausar", "loop detectado", dry_run=False)
    assert r["resultado"] == "ok"


def test_notificar_humano_ok():
    c = FakeClient()
    with patch("ceo.actuator._actuator_enabled", return_value=True), \
         patch("ceo.actuator.notificar_telegram", return_value=True):
        r = ejecutar_accion(c, 1, "notificar_humano", "alerta", dry_run=False)
    assert r["resultado"] == "ok"


def test_kill_switch_no_dispara_2_ok():
    """Con 2 acciones ok recientes, NO bloquea."""
    c = FakeClient(count_actions=2)
    with patch("ceo.actuator._actuator_enabled", return_value=True):
        r = ejecutar_accion(c, 1, "task_rerun", "42", dry_run=False)
    # No debe ser kill_switch (puede ser ok o skip_hysteresis)
    assert r["resultado"] != "kill_switch"


def test_kill_switch_dispara_3_ok():
    """Con 3 acciones ok recientes, bloquea."""
    c = FakeClient(count_actions=3)
    with patch("ceo.actuator._actuator_enabled", return_value=True), \
         patch("ceo.actuator.notificar_telegram", return_value=True):
        r = ejecutar_accion(c, 1, "task_rerun", "42", dry_run=False)
    assert r["resultado"] == "kill_switch"


def test_kill_switch_fail_open():
    """Si Supabase falla, permite la acción."""
    class Broken:
        def table(self, _): raise RuntimeError("boom")
    # No debe explotar
    r = ejecutar_accion(Broken(), 1, "task_rerun", "42", dry_run=True)
    assert r["resultado"] in ("dry_run", "ok", "error_audit_trail")
