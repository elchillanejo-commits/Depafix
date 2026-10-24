"""Smoke test local del endpoint /agencia/ikki/simular (sin red ni Supabase)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.agencia.api import app  # noqa: E402

payload = {
    "cliente_id": "gestalt-medical",
    "cliente_nombre": "Gestalt Medical",
    "rubro": "salud_genetica",
    "presupuesto_pauta_mensual_clp": 1_000_000,
    "horizonte_dias": 30,
    "fee_fijo_clp": 150_000,
    "pct_pauta": 0.15,
    "embudos": [
        {"embudo": "B2C", "porcentaje_presupuesto": 0.60},
        {"embudo": "B2B", "porcentaje_presupuesto": 0.40},
    ],
    "persistir": False,
    "metadatos": {"origen": "smoke_test_local", "entorno": "local"},
}

client = TestClient(app)
response = client.post("/agencia/ikki/simular", json=payload)
data = response.json()

assert response.status_code == 200, data
assert data["persistencia"]["estado"] == "omitida"
assert [item["embudo"] for item in data["embudos"]] == ["B2C", "B2B"]
assert sum(
    item["presupuesto_pauta_mensual_clp"] for item in data["embudos"]
) == 1_000_000
assert data["fee"]["total_facturar_clp"] == 1_300_000
assert data["resumen"]["leads_por_embudo"] == {"B2C": 51, "B2B": 14}

output_path = Path(__file__).with_name("smoke_test_response.json")
output_path.write_text(
    json.dumps(data, ensure_ascii=False, indent=2),
    encoding="utf-8",
)

print(f"HTTP {response.status_code}")
print(f"Respuesta guardada en: {output_path}")
print("Checks: B2C/B2B separados, presupuesto 600k+400k, fee 130k, dry-run OK")
print(json.dumps(data, ensure_ascii=False, indent=2))
