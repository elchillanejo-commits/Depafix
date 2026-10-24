"""
benchmarks.py — Supuestos de medios por embudo para Gestalt Medical.

Los valores son parámetros de simulación, no garantías de resultados.
Deben recalibrarse con datos reales de Meta/Google Ads y del CRM de Ikki.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Literal

from src.agencia.esquemas import Embudo

FUENTE_BENCHMARKS = (
    "Supuestos internos Ikki 2026; recalibrar con Meta Ads, Google Ads y CRM propio."
)
NOTA_SUPUESTOS = (
    "Proyección determinística de escenario. No constituye promesa de resultados "
    "clínicos ni comerciales. El ROAS se calcula solo sobre pauta, sin fee de agencia."
)


@dataclass(frozen=True)
class BenchmarkEmbudo:
    embudo: Embudo
    plataforma_codigo: Literal["Meta", "Google", "TikTok", "Otra"]
    canal_principal: str
    canales_secundarios: tuple[str, ...]
    cpm_clp: int
    ctr: Decimal
    tasa_conversion_lead: Decimal
    tasa_cierre: Decimal
    ticket_promedio_clp: int
    objetivo: str
    publico_objetivo: str
    kpis_objetivo: dict[str, int | float] = field(default_factory=dict)
    fuente: str = FUENTE_BENCHMARKS


BENCHMARKS: dict[Embudo, BenchmarkEmbudo] = {
    "B2C": BenchmarkEmbudo(
        embudo="B2C",
        plataforma_codigo="Meta",
        canal_principal="Meta Ads",
        canales_secundarios=("Google Search",),
        cpm_clp=6_500,
        ctr=Decimal("0.014"),
        tasa_conversion_lead=Decimal("0.040"),
        tasa_cierre=Decimal("0.150"),
        ticket_promedio_clp=320_000,
        objetivo=(
            "Generar leads de pacientes y familias para evaluación genética, "
            "con agenda o contacto por WhatsApp."
        ),
        publico_objetivo=(
            "Personas de 25 a 55 años con antecedentes familiares, síntomas o "
            "derivación médica; cuidadores y familias en Santiago y regiones."
        ),
        kpis_objetivo={
            "cpl_objetivo_clp": 20_000,
            "leads_objetivo_mes": 30,
            "contacto_24h_pct": 80,
        },
    ),
    "B2B": BenchmarkEmbudo(
        embudo="B2B",
        plataforma_codigo="Google",
        canal_principal="Google Ads",
        canales_secundarios=("LinkedIn Ads", "Outbound/email"),
        cpm_clp=24_000,
        ctr=Decimal("0.018"),
        tasa_conversion_lead=Decimal("0.050"),
        tasa_cierre=Decimal("0.150"),
        ticket_promedio_clp=1_200_000,
        objetivo=(
            "Agendar demos y pilotos de optimización clínica con clínicas, "
            "laboratorios y centros médicos."
        ),
        publico_objetivo=(
            "Directores médicos, gerentes de operaciones y dueños de clínicas "
            "o laboratorios con más de 20 profesionales."
        ),
        kpis_objetivo={
            "cpl_objetivo_clp": 40_000,
            "demos_objetivo_mes": 8,
            "cierre_piloto_pct": 12,
        },
    ),
}


def obtener_benchmark(embudo: Embudo) -> BenchmarkEmbudo:
    try:
        return BENCHMARKS[embudo]
    except KeyError as exc:
        raise ValueError(f"Embudo no soportado: {embudo}") from exc
