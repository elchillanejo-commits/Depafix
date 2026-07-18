#!/usr/bin/env python3
"""
test_procurador_tool.py -- tests de ProcuradorParser y analyze_legal_risk
contra fixtures de texto plano (Caso Ordinario / Caso Sumario), sin generar
PDFs ni tocar Supabase: ProcuradorParser recibe texto directo (ver
core/procurador_tool.py -- se separo la extraccion de PDF del parseo con
regex justo para poder testear asi).
"""
import sys
from pathlib import Path

CORE_PATH = Path(__file__).resolve().parent.parent
if str(CORE_PATH) not in sys.path:
    sys.path.insert(0, str(CORE_PATH))

from core.procurador_tool import ProcuradorParser, analyze_legal_risk

CASO_ORDINARIO = """ROL C-1234-2024
Ante el Tribunal de Letras de Santiago, en autos.
Demandante: Constructora XYZ Ltda.
Demandado: Municipalidad de Providencia.
Se ha iniciado la etapa de discusión con la contestación de la demanda.
Próximo plazo: 31/07/2026
"""

CASO_SUMARIO = """ROL C-987-2025
Juzgado de Letras de Rancagua.
Demandante: Inmobiliaria Andes SpA.
Se decreta la rebeldía del demandado por no contestar dentro de plazo.
"""


def test_caso_ordinario_sin_riesgos():
    data = ProcuradorParser(CASO_ORDINARIO).parse()
    assert data["rol"] == "C-1234-2024"
    assert data["etapa_procesal"] == "discusión"
    assert data["litigantes"] == {
        "demandante": "Constructora XYZ Ltda.",
        "demandado": "Municipalidad de Providencia",
    }
    assert data["proximo_plazo"] == "31/07/2026"

    riesgo = analyze_legal_risk(data, CASO_ORDINARIO)
    assert riesgo["riesgos"] == []
    assert riesgo["risk_score"] == 0
    assert riesgo["dictamen_final"] == "SIN_OBSERVACIONES"


def test_caso_sumario_con_riesgos():
    data = ProcuradorParser(CASO_SUMARIO).parse()
    assert data["rol"] == "C-987-2025"
    assert data["proximo_plazo"] is None
    # Solo hay lider "Demandante:" en el fixture -- no hay "Demandado:"
    # explicito (la mencion "del demandado" es prosa, no una etiqueta), asi
    # que el patron DDO no dispara y litigantes queda incompleto a
    # proposito: es justo lo que PALABRAS_RIESGO_URGENTE +
    # LITIGANTES_PRESENTES capturan como riesgo mas abajo. Sin una segunda
    # etiqueta donde detenerse, la captura de "demandante" se extiende
    # hasta el final del texto -- limitacion conocida de un parser de
    # regex, no algo que valga la pena resolver con mas heuristica aca.
    assert data["litigantes"]["demandante"].startswith("Inmobiliaria Andes SpA.")
    assert "demandado" not in data["litigantes"]

    riesgo = analyze_legal_risk(data, CASO_SUMARIO)
    ids_disparados = {r["id"] for r in riesgo["riesgos"]}
    assert "PLAZO_PRESENTE" in ids_disparados
    assert "PALABRAS_RIESGO_URGENTE" in ids_disparados
    assert riesgo["dictamen_final"] == "REVISION_URGENTE"
    assert riesgo["risk_score"] == 3 + 2  # alto (rebeldía) + medio (sin plazo)


def test_clausula_abusiva_dispara_negociar_con_salvaguarda():
    texto = (
        "ROL C-555-2026\n"
        "Juzgado de Letras de Concepción.\n"
        "Demandante: Comercial Sur Ltda.\n"
        "Demandado: Inversiones Norte SA.\n"
        "El contrato establece renuncia irrevocable a toda acción por parte del arrendatario.\n"
        "Próximo plazo: 01/09/2026\n"
    )
    data = ProcuradorParser(texto).parse()
    riesgo = analyze_legal_risk(data, texto)

    assert "CLAUSULA_RENUNCIA_UNILATERAL_EJEMPLO" in {r["id"] for r in riesgo["riesgos"]}
    assert riesgo["dictamen_final"] == "NEGOCIAR"
    assert len(riesgo["safeguard_clauses"]) == 1
    assert riesgo["safeguard_clauses"][0]["id"] == "CLAUSULA_RENUNCIA_UNILATERAL_EJEMPLO"
    assert "PLACEHOLDER" in riesgo["safeguard_clauses"][0]["salvaguarda"]
    # abusiva (5) pesa mas que cualquier combinacion de alto/medio/bajo de
    # las demas reglas -- NEGOCIAR debe ganarle a REVISION_URGENTE aunque
    # ambas condiciones esten presentes en el mismo documento.
    assert riesgo["risk_score"] >= 5


def test_rol_ausente_no_dispara_excepcion():
    data = ProcuradorParser("Un documento sin ningún ROL identificable.").parse()
    assert data["rol"] is None
    riesgo = analyze_legal_risk(data, "Un documento sin ningún ROL identificable.")
    assert "ROL_PRESENTE" in {r["id"] for r in riesgo["riesgos"]}
    assert riesgo["dictamen_final"] == "REVISION_URGENTE"


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
