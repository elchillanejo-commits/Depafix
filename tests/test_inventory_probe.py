"""Tests para inventory_probe con FakeClient."""
from __future__ import annotations

from unittest.mock import patch

from ceo.workers.inventory_probe import (
    UF_REF_2026_CLP,
    UMBRAL_CONCENTRACION_VALOR,
    UMBRAL_DESVIACION_PRECIO,
    _detectar_concentracion_valor,
    _detectar_desviaciones_precio,
    _estado_stock,
    inventory_probe_worker,
)


class FakeResp:
    def __init__(self, data=None):
        self.data = data or []


class FakeQuery:
    def __init__(self, data):
        self._data = data

    def select(self, *a, **k):
        return self

    def eq(self, *a, **k):
        return self

    def gt(self, *a, **k):
        return self

    def limit(self, *a, **k):
        return self

    def order(self, *a, **k):
        return self

    def execute(self):
        return FakeResp(self._data)


class FakeClient:
    def __init__(self, inv=None):
        self._inv = inv or []

    def table(self, name):
        if name == "inventario_real":
            return FakeQuery(self._inv)
        return FakeQuery([])


def _row(sku, stock, smin, cat="Hormigones", precio_uf=5.0, precio=200000):
    return {
        "sku": sku,
        "nombre": sku,
        "stock": stock,
        "stock_min": smin,
        "precio_clp": precio,
        "categoria": cat,
        "codigo_serviu": f"C-{sku}",
        "precio_serviu_uf": precio_uf,
    }


def _run_worker(inv):
    env = {
        "SUPABASE_URL": "http://test",
        "SUPABASE_SERVICE_ROLE_KEY": "test",
    }
    with patch.dict("os.environ", env):
        with patch(
            "ceo.workers.inventory_probe.create_client",
            return_value=FakeClient(inv),
        ):
            with patch("ceo.workers.inventory_probe.registrar_health") as health:
                return inventory_probe_worker(), health


def test_inventory_sin_skus():
    r, health = _run_worker([])
    assert r == {"ok": True, "total_skus": 0, "status": "warn"}
    health.assert_called_once()
    assert health.call_args.args[3] == "warn"
    assert health.call_args.args[5]["motivo"] == "tabla_vacia"


def test_deteccion_bajos():
    inv = [
        _row("SKU-1", 1, 10),
        _row("SKU-2", 2, 10),
        _row("SKU-3", 3, 10),
    ]
    r, health = _run_worker(inv)
    assert r["ok"] is True
    assert r["status"] == "warn"
    assert r["n_bajos"] == 3
    assert r["n_criticos"] == 0
    assert health.call_args.args[5]["n_bajos"] == 3


def test_estado_stock():
    assert _estado_stock(0, 10) == "critico"
    assert _estado_stock(5, 10) == "bajo"
    assert _estado_stock(10, 10) == "ok"
    assert _estado_stock(50, 10) == "ok"
    assert _estado_stock(51, 10) == "sobre"


def test_deteccion_desviacion_precio():
    skus = [_row("SKU-1", 10, 5, precio_uf=1.0, precio=100000)]
    r = _detectar_desviaciones_precio(skus)
    assert len(r) == 1
    assert r[0]["pct"] > UMBRAL_DESVIACION_PRECIO * 100


def test_concentracion_valor():
    skus = [
        _row("SKU-1", 100, 5, precio=1000),
        _row("SKU-2", 1, 5, precio=1000),
    ]
    r = _detectar_concentracion_valor(skus)
    assert r is not None
    assert r["sku"] == "SKU-1"
    assert r["pct"] > UMBRAL_CONCENTRACION_VALOR * 100


def test_uf_referencia():
    assert float(UF_REF_2026_CLP) == 39779.29
