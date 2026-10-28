from __future__ import annotations

from unittest.mock import patch

from ceo.actuator import ejecutar_accion
from ceo.diagnostician import Diagnosis, DiagResult


class FakeResp:
    def __init__(self, data=None, count=None):
        self.data = data if data is not None else []
        self.count = count


class FakeClient:
    def __init__(self, count_actions=0):
        self._count = count_actions
        self._name = None
        self._last_insert = None
        self._last_update = None
        self.inserted = []
        self.updated = []
        self._next_id = 100

    def table(self, name):
        self._name = name
        self._last_insert = None
        self._last_update = None
        return self

    def select(self, *a, **k):
        return self

    def insert(self, d):
        self._last_insert = d
        self._next_id += 1
        return self

    def update(self, d):
        self._last_update = d
        return self

    def eq(self, *a, **k):
        return self

    def gte(self, *a, **k):
        return self

    def order(self, *a, **k):
        return self

    def limit(self, *a, **k):
        return self

    def execute(self):
        if self._name == "ceo_actions":
            if self._last_insert is not None:
                row = {"id": self._next_id, **self._last_insert}
                self.inserted.append(row)
                self._last_insert = None
                return FakeResp(data=[{"id": row["id"]}])
            if self._last_update is not None:
                self.updated.append(self._last_update)
                self._last_update = None
                return FakeResp()
            return FakeResp(count=self._count)
        return FakeResp()


def _diag(accion="task_rerun", confianza=0.9, requiere_humano=False,
          target="42", diagnostico="fallo de prueba", ok=True,
          motivo="Diagnóstico exitoso"):
    diagnosis = None
    if ok:
        diagnosis = Diagnosis(
            diagnostico=diagnostico,
            accion_sugerida=accion,
            target=target,
            confianza=confianza,
            requiere_humano=requiere_humano,
        )
    return DiagResult(ok=ok, motivo=motivo, diagnosis=diagnosis)


def test_dry_run_no_ejecuta():
    c = FakeClient()
    with patch("ceo.actuator._actuator_enabled", return_value=False):
        r = ejecutar_accion(c, _diag())
    assert r["resultado"] == "dry_run"


def test_accion_fuera_whitelist():
    c = FakeClient()
    dx = Diagnosis.model_construct(
        diagnostico="test", accion_sugerida="rm_rf_slash",
        target="/", confianza=0.9, requiere_humano=False,
    )
    r = ejecutar_accion(
        c, DiagResult(ok=True, motivo="Diagnóstico exitoso", diagnosis=dx)
    )
    assert r["resultado"] == "rechazada_whitelist"
    assert r["ok"] is False


def test_target_con_caracteres_invalidos():
    c = FakeClient()
    r = ejecutar_accion(c, _diag(target="42; rm -rf ~"))
    assert r["resultado"] == "target_invalido"
    assert r["ok"] is False


def test_hysteresis_restart():
    c = FakeClient(count_actions=2)  # ya hay 2 restarts hoy
    with patch("ceo.actuator._actuator_enabled", return_value=True):
        r = ejecutar_accion(
            c, _diag(accion="systemctl_restart", target="depafix-trading")
        )
    assert r["resultado"] == "skip_hysteresis"


def test_task_rerun_ok():
    c = FakeClient()
    with patch("ceo.actuator._actuator_enabled", return_value=True):
        r = ejecutar_accion(c, _diag(), dry_run=False)
    assert r["resultado"] == "ok"
    assert r["ok"] is True


def test_bot_pausar_ok():
    c = FakeClient()
    with patch("ceo.actuator._actuator_enabled", return_value=True):
        r = ejecutar_accion(
            c, _diag(accion="bot_pausar", target="loop detectado"), dry_run=False
        )
    assert r["resultado"] == "ok"


def test_notificar_humano_ok():
    c = FakeClient()
    with patch("ceo.actuator._actuator_enabled", return_value=True), \
         patch("ceo.actuator.notificar_telegram", return_value=True):
        r = ejecutar_accion(
            c, _diag(accion="notificar_humano", target="alerta"), dry_run=False
        )
    assert r["resultado"] == "ok"


def test_confianza_baja_fuerza_notificar_humano():
    c = FakeClient()
    with patch("ceo.actuator._actuator_enabled", return_value=True), \
         patch("ceo.actuator.notificar_telegram", return_value=True) as tg:
        r = ejecutar_accion(
            c, _diag(accion="task_rerun", confianza=0.5), dry_run=False
        )
    assert r["accion"] == "notificar_humano"
    assert r["resultado"] == "ok"
    tg.assert_called_once()
    assert c.updated[-1]["resultado"] == "ok"
    payload = c.updated[-1]["payload"]
    assert payload["forzada"] is True
    assert payload["accion_original"] == "task_rerun"
    assert payload["confianza"] == 0.5


def test_requiere_humano_fuerza_notificar_humano():
    c = FakeClient()
    with patch("ceo.actuator._actuator_enabled", return_value=True), \
         patch("ceo.actuator.notificar_telegram", return_value=True) as tg:
        r = ejecutar_accion(
            c,
            _diag(accion="bot_pausar", confianza=0.95, requiere_humano=True),
            dry_run=False,
        )
    assert r["accion"] == "notificar_humano"
    assert r["resultado"] == "ok"
    tg.assert_called_once()


def test_confianza_limite_no_fuerza():
    c = FakeClient()
    with patch("ceo.actuator._actuator_enabled", return_value=True), \
         patch("ceo.actuator._hacer_task_rerun", return_value=("ok", "x")):
        r = ejecutar_accion(
            c, _diag(accion="task_rerun", confianza=0.6), dry_run=False
        )
    assert r["accion"] == "task_rerun"


def test_ninguna_registra_ok_sin_ejecutar():
    c = FakeClient()
    with patch("ceo.actuator._actuator_enabled", return_value=True), \
         patch("ceo.actuator._hacer_notificar_humano") as nh, \
         patch("ceo.actuator._hacer_task_rerun") as tr:
        r = ejecutar_accion(
            c,
            _diag(accion="ninguna", target=None, diagnostico="todo en orden"),
            dry_run=False,
        )
    assert r["resultado"] == "ok"
    assert r["accion"] == "ninguna"
    assert r["motivo"] == "todo en orden"
    nh.assert_not_called()
    tr.assert_not_called()
    fila = c.inserted[-1]
    assert fila["resultado"] == "ok"
    assert fila["payload"]["motivo"] == "todo en orden"
    assert fila["payload"]["sin_accion"] is True
    assert c.updated == []


def test_diagnostico_fallido_no_ejecuta():
    c = FakeClient()
    r = ejecutar_accion(
        c, _diag(ok=False, motivo="Kimi no disponible"), dry_run=False
    )
    assert r["ok"] is False
    assert r["resultado"] == "diagnostico_fallido"
    assert c.inserted == []
    assert c.updated == []


def test_kill_switch_no_dispara_2_ok():
    """Con 2 acciones ok recientes, NO bloquea."""
    c = FakeClient(count_actions=2)
    with patch("ceo.actuator._actuator_enabled", return_value=True):
        r = ejecutar_accion(c, _diag(), dry_run=False)
    # No debe ser kill_switch (puede ser ok o skip_hysteresis)
    assert r["resultado"] != "kill_switch"


def test_kill_switch_dispara_3_ok():
    """Con 3 acciones ok recientes, bloquea."""
    c = FakeClient(count_actions=3)
    with patch("ceo.actuator._actuator_enabled", return_value=True), \
         patch("ceo.actuator.notificar_telegram", return_value=True):
        r = ejecutar_accion(c, _diag(), dry_run=False)
    assert r["resultado"] == "kill_switch"


def test_kill_switch_fail_open():
    """Si Supabase falla, permite la acción."""
    class Broken:
        def table(self, _): raise RuntimeError("boom")
    # No debe explotar
    r = ejecutar_accion(Broken(), _diag(), dry_run=True)
    assert r["resultado"] in ("dry_run", "ok", "error_audit_trail")
