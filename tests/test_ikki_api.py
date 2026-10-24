from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient

from src.agencia import api
from src.agencia.esquemas import PersistenciaResultado


client = TestClient(api.app)


def _payload(**overrides):
    data = {
        "cliente_id": "gestalt-medical",
        "cliente_nombre": "Gestalt Medical",
        "rubro": "salud_genetica",
        "presupuesto_pauta_mensual_clp": 1_000_000,
        "persistir": False,
    }
    data.update(overrides)
    return data


def test_health():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["modelo"] == "Contexto-Diagnóstico-Acción"


def test_simulacion_b2c_b2b_default():
    response = client.post("/agencia/ikki/simular", json=_payload())
    assert response.status_code == 200, response.text

    data = response.json()
    assert data["cliente_id"] == "gestalt-medical"
    assert data["modelo_cda"] == "Contexto-Diagnóstico-Acción"
    assert data["persistencia"]["estado"] == "omitida"
    assert [item["embudo"] for item in data["embudos"]] == ["B2C", "B2B"]

    presupuestos = [
        item["presupuesto_pauta_mensual_clp"] for item in data["embudos"]
    ]
    assert presupuestos == [600_000, 400_000]
    assert sum(presupuestos) == data["presupuesto_total_pauta_clp"]

    fee = data["fee"]
    assert fee["comision_agencia_clp"] == 150_000
    assert fee["total_facturar_clp"] == 1_300_000
    assert fee["margen_agencia_clp"] == 300_000
    assert sum(item["fee"]["margen_agencia_clp"] for item in data["embudos"]) == 300_000

    assert data["resumen"]["leads_por_embudo"] == {"B2C": 51, "B2B": 14}
    assert data["resumen"]["clientes_por_embudo"] == {"B2C": 7, "B2B": 2}
    assert data["resumen"]["roas_estimado"] == 4.64

    for embudo in data["embudos"]:
        assert embudo["cda"]["contexto"]
        assert embudo["cda"]["diagnostico"]
        assert embudo["cda"]["accion"]["cta"]
        assert embudo["cumplimiento"]
        assert len(embudo["plan_30_dias"]) == 4
        assert len(embudo["creatividades"]) == 3


def test_simulacion_split_personalizado():
    response = client.post(
        "/agencia/ikki/simular",
        json=_payload(
            presupuesto_pauta_mensual_clp=900_000,
            embudos=[
                {"embudo": "B2C", "porcentaje_presupuesto": 0.5},
                {"embudo": "B2B", "porcentaje_presupuesto": 0.5},
            ],
        ),
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert [item["presupuesto_pauta_mensual_clp"] for item in data["embudos"]] == [
        450_000,
        450_000,
    ]


def test_distribucion_invalida_retorna_422():
    response = client.post(
        "/agencia/ikki/simular",
        json=_payload(
            embudos=[
                {"embudo": "B2C", "porcentaje_presupuesto": 0.7},
                {"embudo": "B2B", "porcentaje_presupuesto": 0.7},
            ]
        ),
    )
    assert response.status_code == 422


def test_persistencia_controlada(monkeypatch):
    class FakeRepo:
        def guardar_simulacion(self, simulacion):
            return PersistenciaResultado(
                solicitada=True,
                estado="guardada",
                motivo="fake",
                campanas_guardadas=len(simulacion.embudos),
                presupuestos_guardados=len(simulacion.embudos),
                ids=["campana-b2c", "campana-b2b"],
            )

    monkeypatch.setattr(api, "construir_repositorio", lambda: FakeRepo())
    response = client.post(
        "/agencia/ikki/simular", json=_payload(persistir=True)
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["persistencia"]["estado"] == "guardada"
    assert data["persistencia"]["campanas_guardadas"] == 2


def test_lead_controlado(monkeypatch):
    lead_id = uuid4()

    class FakeRepo:
        def guardar_lead(self, lead):
            return lead_id

    monkeypatch.setattr(api, "construir_repositorio", lambda: FakeRepo())
    response = client.post(
        "/agencia/ikki/leads",
        json={
            "cliente_id": "gestalt-medical",
            "embudo": "B2C",
            "tipo_lead": "paciente",
            "nombre": "Paciente Demo",
            "email": "demo@example.com",
            "origen_plataforma": "meta",
            "utm_source": "meta",
            "utm_campaign": "b2c-genetica",
            "consentimiento_marketing": True,
        },
    )
    assert response.status_code == 201, response.text
    assert response.json() == {
        "lead_id": str(lead_id),
        "estado": "guardado",
        "embudo": "B2C",
        "origen_plataforma": "meta",
    }


def test_fee_agencia_15_pct():
    response = client.post(
        "/api/v1/simular", json={"presupuesto_base": 1_000_000}
    )
    assert response.status_code == 200, response.text
    assert response.json() == {
        "status": "success",
        "presupuesto_base_clp": 1_000_000,
        "pct_fee_agencia": 0.15,
        "fee_agencia_clp": 150_000,
        "total_cliente_clp": 1_150_000,
        "moneda": "CLP",
    }


def test_fee_agencia_presupuesto_invalido():
    response = client.post("/api/v1/simular", json={"presupuesto_base": 0})
    assert response.status_code == 422


class FakeMotorCasos:
    def __init__(self, caso):
        self.caso = caso
        self.rubros = []

    def obtener_caso_exito(self, rubro):
        self.rubros.append(rubro)
        return self.caso


def test_legacy_simular(monkeypatch):
    monkeypatch.setattr(api, "construir_motor_casos", lambda: FakeMotorCasos({}))
    response = client.post(
        "/api/v1/simular",
        json={
            "cliente_id": "inmobiliaria_demo",
            "rubro": "inmobiliaria",
            "presupuesto_pauta": 500_000,
        },
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["status"] == "success"
    assert data["campaña_generada"]["cliente_id"] == "inmobiliaria_demo"
    assert data["campaña_generada"]["configuracion"]["fee_calculado"]["pauta_neta"] == 500_000
    assert data["campaña_generada"]["configuracion"]["caso_exito"] == {}


def test_legacy_simular_inyecta_caso_exito(monkeypatch):
    caso = {
        "industria": "Inmobiliaria",
        "descripcion": "1.562 leads generados con $14.4M.",
        "cpl_promedio_clp": 7688,
        "mejor_creatividad": "Video Testimonio",
        "fuente": "Caso Cordillera - Chile 2026",
    }
    fake = FakeMotorCasos(caso)
    monkeypatch.setattr(api, "construir_motor_casos", lambda: fake)
    response = client.post(
        "/api/v1/simular",
        json={
            "cliente_id": "inmobiliaria_demo",
            "rubro": "inmobiliaria",
            "presupuesto_pauta": 500_000,
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["campaña_generada"]["configuracion"]["caso_exito"] == caso
    assert fake.rubros == ["inmobiliaria"]


def test_legacy_simular_caso_exito_falla_devuelve_vacio(monkeypatch):
    class MotorRoto:
        def obtener_caso_exito(self, rubro):
            raise RuntimeError("Supabase caído")

    monkeypatch.setattr(api, "construir_motor_casos", lambda: MotorRoto())
    response = client.post(
        "/api/v1/simular",
        json={"cliente_id": "inmobiliaria_demo", "rubro": "inmobiliaria", "presupuesto_pauta": 500_000},
    )
    assert response.status_code == 200, response.text
    assert response.json()["campaña_generada"]["configuracion"]["caso_exito"] == {}
