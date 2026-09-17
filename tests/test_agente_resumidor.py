"""Tests del agente resumidor híbrido: extracción de PDF, resumen mockeado,
persistencia en Supabase, y (manual) resumen real vía Claude."""
import os
import sys
from pathlib import Path

import pytest
from reportlab.pdfgen import canvas

PROJECT_ROOT = Path(__file__).resolve().parent.parent
AGENTE_DIR = PROJECT_ROOT / "06_AGENTES" / "resumidor_ocr"
sys.path.insert(0, str(AGENTE_DIR))

import agente_resumidor  # noqa: E402
from core.db_manager import DatabaseManager  # noqa: E402

TEXTO_PDF = (
    "DepaFix es una plataforma de agentes de inteligencia artificial que automatiza "
    "tramites legales y de construccion en Chile, integrando Supabase para "
    "persistencia de datos y Railway para el despliegue de sus servicios."
)


@pytest.fixture
def pdf_de_prueba(tmp_path) -> Path:
    ruta = tmp_path / "documento_prueba.pdf"
    c = canvas.Canvas(str(ruta))
    y = 800
    for linea in TEXTO_PDF.split(", "):
        c.drawString(50, y, linea.strip())
        y -= 20
    c.save()
    return ruta


def test_extraer_texto_pdf(pdf_de_prueba):
    texto = agente_resumidor.extraer_texto_pdf(str(pdf_de_prueba))
    assert len(texto) > 10
    assert "DepaFix" in texto
    assert "Supabase" in texto


def test_resumen_mockeado_sin_llamar_api():
    """generar_resumen_mock no llama a la red -- valida el camino de
    respaldo que usa resumir_y_guardar cuando no hay API key o falla Claude."""
    resumen = agente_resumidor.generar_resumen_mock(TEXTO_PDF)
    assert resumen.startswith("[RESUMEN MOCK")
    assert "DepaFix" in resumen


def test_persistencia_en_supabase():
    """Inserta un resumen directamente (sin pasar por Claude) y verifica que
    guardar_resumen devuelva un ID real y que el registro exista en la tabla."""
    db = DatabaseManager().get_service_client()
    resumen_id = agente_resumidor.guardar_resumen(
        texto_original=TEXTO_PDF,
        resumen="[RESUMEN MOCK — Claude API no disponible]\n" + TEXTO_PDF[:100],
        modelo="test-persistencia",
        metadata={"fuente": "test_persistencia_en_supabase"},
    )
    try:
        assert isinstance(resumen_id, int)
        fila = (
            db.table("resumenes")
            .select("modelo_usado,resumen")
            .eq("id", resumen_id)
            .execute()
            .data[0]
        )
        assert fila["modelo_usado"] == "test-persistencia"
        assert fila["resumen"].startswith("[RESUMEN MOCK")
    finally:
        # No dejar basura de test en la tabla de producción.
        db.table("resumenes").delete().eq("id", resumen_id).execute()


@pytest.mark.skip(
    reason="Llama a la API real de Claude (consume crédito) y hace un insert "
    "real en Supabase. Ejecutar manualmente con: "
    "pytest tests/test_agente_resumidor.py -k resumen_real_api --no-skip "
    "(o sacando el @pytest.mark.skip) cuando se quiera validar end-to-end."
)
def test_resumen_real_api(pdf_de_prueba):
    assert os.getenv("CLAUDE_API_KEY") or os.getenv("ANTHROPIC_API_KEY"), (
        "Configurá CLAUDE_API_KEY/ANTHROPIC_API_KEY en .env antes de correr este test"
    )
    texto_extraido = agente_resumidor.extraer_texto_pdf(str(pdf_de_prueba))

    resultado = agente_resumidor.resumir_y_guardar(
        texto_extraido, max_tokens=100, fuente=str(pdf_de_prueba)
    )

    assert resultado["modelo_usado"] == agente_resumidor.CLAUDE_MODEL
    assert not resultado["resumen"].startswith("[RESUMEN MOCK")
    assert resultado["id"] is not None
