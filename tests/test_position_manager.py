from __future__ import annotations

import pandas as pd

from src.trading.position_manager import (
    HARD_STOP_PCT,
    Posicion,
    _calcular_stop,
    actualizar_stop,
    cerrar_posicion,
    debe_cerrar,
    df_desde_velas,
    get_posicion_abierta,
    registrar_posicion,
)


class FakeResp:
    def __init__(self, data): self.data = data


class FakeClient:
    def __init__(self, rows=None, insert_ret=None):
        self._rows = rows or []
        self._insert_ret = insert_ret or []
        self.last_insert = None
        self.last_update = None
        self.last_delete = None
    def table(self, _): return self
    def select(self, _): return self
    def insert(self, d): self.last_insert = d; return self
    def update(self, d): self.last_update = d; return self
    def delete(self): self.last_delete = True; return self
    def eq(self, *a): return self
    def order(self, *a, **k): return self
    def limit(self, _): return self
    def execute(self):
        if self.last_insert is not None: return FakeResp(self._insert_ret)
        return FakeResp(self._rows)


def _df(minimo=100.0, n=10):
    closes = [minimo + i for i in range(n)]
    return pd.DataFrame({
        "open": closes,
        "high": [c + 1 for c in closes],
        "low":  [c - 1 for c in closes],
        "close": closes,
        "volume": [1] * n,
    })


def test_get_posicion_abierta_sin_historial():
    client = FakeClient(rows=[])
    assert get_posicion_abierta(client, "BTC/USD") is None


def test_get_posicion_abierta_con_fila():
    client = FakeClient(rows=[{
        "id": "abc-123", "activo": "BTC/USD",
        "entry_price": 100.0, "cantidad": 0.5, "posicion_usd": 0.89,
        "current_stop_loss": 95.0, "hard_stop_loss": 95.0,
        "buy_order_id": None,
    }])
    p = get_posicion_abierta(client, "BTC/USD")
    assert p is not None
    assert p.id == "abc-123"
    assert p.current_stop_loss == 95.0


def test_get_posicion_abierta_error_no_lanza():
    class Broken:
        def table(self, _): raise RuntimeError("boom")
    assert get_posicion_abierta(Broken(), "BTC/USD") is None


def test_registrar_posicion_ok():
    client = FakeClient(insert_ret=[{"id": "new-uuid"}])
    pid = registrar_posicion(client, "BTC/USD", 100.0, 0.5, 0.89)
    assert pid == "new-uuid"
    assert client.last_insert["activo"] == "BTC/USD"
    assert client.last_insert["hard_stop_loss"] == 100.0 * (1 - HARD_STOP_PCT)


def test_registrar_posicion_con_stop_inicial():
    client = FakeClient(insert_ret=[{"id": "x"}])
    registrar_posicion(client, "BTC/USD", 100.0, 0.5, 0.89, stop_inicial=97.0)
    assert client.last_insert["current_stop_loss"] == 97.0
    assert client.last_insert["hard_stop_loss"] == 97.0


def test_cerrar_posicion_ok():
    client = FakeClient()
    assert cerrar_posicion(client, "abc-123") is True
    assert client.last_delete is True


def test_actualizar_stop_ok():
    client = FakeClient()
    assert actualizar_stop(client, "abc-123", 98.0) is True
    assert client.last_update["current_stop_loss"] == 98.0
    assert "last_updated_at" in client.last_update


def test_debe_cerrar_sin_stop_previo():
    df = _df(100.0)
    p = Posicion("id1", "BTC/USD", 100.0, 0.5, 0.89, 95.0, 95.0, None)
    cerrar, nuevo_stop, motivo = debe_cerrar(df, p, tipo="atr")
    assert cerrar is False
    assert nuevo_stop >= 95.0


def test_debe_cerrar_stop_rompe():
    closes = [110.0, 108.0, 105.0, 100.0, 95.0, 90.0, 85.0, 80.0]
    df = pd.DataFrame({
        "open": closes,
        "high": [c + 1 for c in closes],
        "low":  [c - 1 for c in closes],
        "close": closes,
        "volume": [1] * len(closes),
    })
    p = Posicion("id1", "BTC/USD", 110.0, 0.5, 0.89, 108.0, 104.5, None)
    cerrar, nuevo_stop, motivo = debe_cerrar(df, p, tipo="bar")
    assert cerrar is True
    assert "trailing_stop_bar" in motivo


def test_debe_cerrar_stop_no_baja():
    closes = [100, 102, 104, 106, 108, 110, 112, 114]
    df = pd.DataFrame({
        "open": closes,
        "high": [c + 1 for c in closes],
        "low":  [c - 1 for c in closes],
        "close": closes,
        "volume": [1] * len(closes),
    })
    p = Posicion("id1", "BTC/USD", 100.0, 0.5, 0.89, 105.0, 95.0, None)
    _, nuevo_stop, _ = debe_cerrar(df, p, tipo="ema")
    assert nuevo_stop >= 105.0


def test_calcular_stop_tipos():
    df = _df(100.0)
    assert _calcular_stop(df, "bar") > 0
    assert _calcular_stop(df, "atr") > 0
    assert _calcular_stop(df, "ema") > 0


def test_df_desde_velas_renombra_columnas():
    velas = [{
        "tiempo": "2026-10-04T10:00:00+00:00",
        "apertura": 100.0, "maximo": 101.0, "minimo": 99.0,
        "cierre": 100.5, "volumen": 10.0,
    }]
    df = df_desde_velas(velas)
    assert "close" in df.columns
    assert df.iloc[0]["close"] == 100.5
