"""
esquemas.py — Contratos Pydantic del módulo Ikki.

Separa la capa HTTP de la lógica de negocio. Cualquier cambio de contrato
(request/response) se hace aquí y no en el motor ni en el repositorio.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

Embudo = Literal["B2C", "B2B"]


def _distribucion_default() -> list["DistribucionEmbudo"]:
    return [
        DistribucionEmbudo(embudo="B2C", porcentaje_presupuesto=0.60),
        DistribucionEmbudo(embudo="B2B", porcentaje_presupuesto=0.40),
    ]


class DistribucionEmbudo(BaseModel):
    """Participación del presupuesto de pauta asignada a un embudo."""

    model_config = ConfigDict(extra="forbid")

    embudo: Embudo
    porcentaje_presupuesto: float = Field(
        ...,
        gt=0,
        le=1,
        description="Fracción del presupuesto total (0.60 = 60%).",
    )
    objetivo: str | None = Field(
        default=None,
        description="Objetivo comercial específico; si se omite se usa el playbook Ikki.",
    )
    publico_objetivo: str | None = Field(
        default=None,
        description="Público objetivo específico; si se omite se usa el playbook Ikki.",
    )


class SimulacionRequest(BaseModel):
    """Entrada del endpoint POST /agencia/ikki/simular."""

    model_config = ConfigDict(extra="forbid")

    cliente_id: str = Field(
        default="gestalt-medical",
        min_length=2,
        max_length=120,
        description="Identificador del cliente en el CRM.",
    )
    cliente_nombre: str = Field(
        default="Gestalt Medical",
        min_length=2,
        max_length=200,
        description="Nombre comercial del cliente.",
    )
    rubro: str = Field(
        default="salud_genetica",
        min_length=2,
        max_length=120,
        description="Rubro o vertical de negocio.",
    )
    presupuesto_pauta_mensual_clp: int = Field(
        ...,
        gt=0,
        le=10_000_000_000,
        description="Inversión mensual total en pauta, en CLP.",
    )
    horizonte_dias: int = Field(
        default=30,
        ge=7,
        le=90,
        description="Ventana de simulación en días.",
    )
    moneda: Literal["CLP"] = "CLP"
    fee_fijo_clp: int = Field(
        default=150_000,
        ge=0,
        description="Fee fijo mensual de la agencia, en CLP.",
    )
    pct_pauta: float = Field(
        default=0.15,
        ge=0,
        le=1,
        description="Comisión de agencia sobre la pauta (0.15 = 15%).",
    )
    embudos: list[DistribucionEmbudo] = Field(
        default_factory=_distribucion_default,
        min_length=1,
        max_length=2,
        description="Distribución del presupuesto entre B2C y B2B.",
    )
    persistir: bool = Field(
        default=False,
        description="Si es true, guarda campañas y presupuestos en Supabase.",
    )
    metadatos: dict[str, Any] = Field(
        default_factory=dict,
        description="Contexto libre para trazabilidad (campaña, fuente, etc.).",
    )

    @model_validator(mode="after")
    def validar_distribucion(self) -> "SimulacionRequest":
        tipos = [item.embudo for item in self.embudos]
        if len(tipos) != len(set(tipos)):
            raise ValueError("No se puede repetir un embudo en la distribución.")
        suma = sum(item.porcentaje_presupuesto for item in self.embudos)
        if abs(suma - 1.0) > 1e-4:
            raise ValueError(
                f"La distribución debe sumar 1.0; recibido: {suma:.4f}."
            )
        return self


class ProspectoLegacy(BaseModel):
    """Contrato histórico de /api/v1/simular (compatibilidad dashboard)."""

    model_config = ConfigDict(extra="ignore")

    cliente_id: str
    rubro: str
    presupuesto_pauta: int = Field(gt=0)


class FeeGlobal(BaseModel):
    fee_fijo_clp: int
    pct_pauta: float
    comision_agencia_clp: int
    total_facturar_clp: int
    margen_agencia_clp: int


class FeeEmbudo(BaseModel):
    fee_fijo_asignado_clp: int
    comision_agencia_clp: int
    total_facturar_clp: int
    margen_agencia_clp: int


class BenchmarkResponse(BaseModel):
    plataforma_codigo: Literal["Meta", "Google", "TikTok", "Otra"]
    canal_principal: str
    canales_secundarios: list[str]
    cpm_clp: int
    cpc_estimado_clp: int
    ctr_pct: float
    tasa_conversion_lead_pct: float
    tasa_cierre_pct: float
    ticket_promedio_clp: int
    fuente: str


class ProyeccionesEmbudo(BaseModel):
    pauta_simulada_clp: int
    impresiones_estimadas: int
    clics_estimados: int
    leads_estimados: int
    clientes_estimados: int
    cpl_clp: int | None
    cac_clp: int | None
    ingresos_estimados_clp: int
    roas_estimado: float | None
    tasa_clics_pct: float
    tasa_conversion_lead_pct: float
    tasa_cierre_pct: float


class PlanItem(BaseModel):
    semana: str
    accion: str
    kpi: str


class Creatividad(BaseModel):
    formato: str
    titulo: str
    cuerpo: str
    cta: str


class AccionCDA(BaseModel):
    oferta: str
    canales: list[str]
    mensajes: list[str]
    landing: str
    cta: str
    seguimiento: list[str]
    kpis: dict[str, int | float]


class CDA(BaseModel):
    contexto: str
    diagnostico: str
    accion: AccionCDA


class EmbudoResultado(BaseModel):
    embudo: Embudo
    nombre: str
    objetivo: str
    publico_objetivo: str
    participacion_pct: float
    presupuesto_pauta_mensual_clp: int
    presupuesto_diario_clp: int
    canal_principal: str
    canales_secundarios: list[str]
    cda: CDA
    benchmarks: BenchmarkResponse
    proyecciones: ProyeccionesEmbudo
    fee: FeeEmbudo
    plan_30_dias: list[PlanItem]
    creatividades: list[Creatividad]
    cumplimiento: list[str]


class ResumenGlobal(BaseModel):
    presupuesto_total_pauta_clp: int
    pauta_simulada_clp: int
    impresiones_estimadas: int
    clics_estimados: int
    leads_estimados: int
    clientes_estimados: int
    cpl_promedio_clp: int | None
    cac_promedio_clp: int | None
    ingresos_estimados_clp: int
    roas_estimado: float | None
    leads_por_embudo: dict[str, int]
    clientes_por_embudo: dict[str, int]


class SupuestosSimulacion(BaseModel):
    fuente_benchmarks: str
    nota: str
    horizonte_dias: int
    modelo_atribucion: str
    moneda: Literal["CLP"]
    version_modelo: str


class PersistenciaResultado(BaseModel):
    solicitada: bool
    estado: Literal["omitida", "guardada", "error"]
    motivo: str | None = None
    campanas_guardadas: int = 0
    presupuestos_guardados: int = 0
    ids: list[str] = Field(default_factory=list)


class SimulacionResponse(BaseModel):
    simulacion_id: UUID
    cliente_id: str
    cliente_nombre: str
    rubro: str
    fecha_simulacion: date
    periodo_mes: date
    horizonte_dias: int
    moneda: Literal["CLP"]
    modelo_cda: str
    presupuesto_total_pauta_clp: int
    fee: FeeGlobal
    embudos: list[EmbudoResultado]
    resumen: ResumenGlobal
    supuestos: SupuestosSimulacion
    metadatos: dict[str, Any] = Field(default_factory=dict)
    persistencia: PersistenciaResultado


class LeadRequest(BaseModel):
    """Entrada para registrar un lead especializado con procedencia."""

    model_config = ConfigDict(extra="forbid")

    cliente_id: str = Field(default="gestalt-medical", min_length=2)
    campana_id: UUID | None = None
    embudo: Embudo
    tipo_lead: Literal[
        "paciente", "familiar", "clinica", "laboratorio", "centro_medico", "otro"
    ] = "otro"
    nombre: str = Field(min_length=2, max_length=200)
    email: str | None = Field(default=None, max_length=320)
    telefono: str | None = Field(default=None, max_length=40)
    empresa: str | None = Field(default=None, max_length=200)
    rubro: str | None = Field(default=None, max_length=120)
    origen_plataforma: Literal[
        "meta", "google", "linkedin", "tiktok", "organico", "referido", "evento", "otro"
    ] = "otro"
    origen_campana: str | None = Field(default=None, max_length=200)
    origen_anuncio: str | None = Field(default=None, max_length=200)
    origen_conjunto: str | None = Field(default=None, max_length=200)
    utm_source: str | None = Field(default=None, max_length=200)
    utm_medium: str | None = Field(default=None, max_length=200)
    utm_campaign: str | None = Field(default=None, max_length=200)
    utm_content: str | None = Field(default=None, max_length=200)
    utm_term: str | None = Field(default=None, max_length=200)
    pagina_aterrizaje: str | None = Field(default=None, max_length=500)
    referrer: str | None = Field(default=None, max_length=500)
    consentimiento_marketing: bool = False
    consentimiento_version: str | None = Field(default=None, max_length=50)
    idempotency_key: str | None = Field(default=None, max_length=200)
    metadatos: dict[str, Any] = Field(default_factory=dict)


class LeadResponse(BaseModel):
    lead_id: UUID
    estado: Literal["guardado"]
    embudo: Embudo
    origen_plataforma: str
