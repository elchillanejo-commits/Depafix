"""
api.py — Capa HTTP del Agente Ikki.

Endpoints:
- POST /agencia/ikki/simular   Simulación CDA B2C + B2B (principal).
- POST /agencia/ikki/leads     Registro de leads con procedencia.
- POST /api/v1/simular         Fee de agencia (15%) o adaptador legacy.
- GET  /                       Health check.

La lógica de negocio vive en motor_cda.py y la persistencia en
repositorio_ikki.py. Esta capa solo traduce HTTP <-> contratos.
"""
from __future__ import annotations

import logging
from functools import lru_cache

from fastapi import FastAPI, HTTPException, status

from src.agencia.esquemas import (
    DistribucionEmbudo,
    LeadRequest,
    LeadResponse,
    ProspectoLegacy,
    SimulacionRequest,
    SimulacionResponse,
)
from src.agencia.motor_cda import MODELO_CDA, MotorCDA
from src.agencia.motor_ikki import AgenciaIkkiMotor, FeeAgenciaRequest, MotorIkki
from src.agencia.repositorio_ikki import ErrorPersistencia, RepositorioIkki

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Ikki Agency API",
    description="Simulación de campañas CDA y telemetría para Gestalt Medical.",
    version="2.0.0",
)

motor = MotorCDA()
motor_fee = MotorIkki()


def construir_repositorio() -> RepositorioIkki:
    """Factory testeable para la capa de persistencia."""
    return RepositorioIkki()


@lru_cache(maxsize=1)
def construir_motor_casos() -> AgenciaIkkiMotor:
    """Factory testeable para la lectura de casos_exito (Supabase)."""
    return AgenciaIkkiMotor()


def obtener_caso_exito(rubro: str) -> dict:
    """Caso de éxito del rubro desde Supabase, o {} si no hay o falla."""
    try:
        return construir_motor_casos().obtener_caso_exito(rubro) or {}
    except Exception as exc:
        logger.warning("No se pudo obtener caso de éxito para %s: %s", rubro, exc)
        return {}


@app.get("/")
def health_check() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "Ikki Agency API",
        "version": "2.0.0",
        "modelo": MODELO_CDA,
    }


@app.post(
    "/agencia/ikki/simular",
    response_model=SimulacionResponse,
    status_code=status.HTTP_200_OK,
    summary="Simular campaña CDA con embudos B2C y B2B",
)
def simular_campana(request: SimulacionRequest) -> SimulacionResponse:
    try:
        resultado = motor.simular(request)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc

    if not request.persistir:
        logger.info(
            "Simulación dry-run %s para %s",
            resultado.simulacion_id,
            request.cliente_id,
        )
        return resultado

    try:
        persistencia = construir_repositorio().guardar_simulacion(resultado)
    except ErrorPersistencia as exc:
        logger.error("Persistencia fallida: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"codigo": "persistencia_error", "mensaje": str(exc)},
        ) from exc

    logger.info(
        "Simulación %s persistida para %s",
        resultado.simulacion_id,
        request.cliente_id,
    )
    return resultado.model_copy(update={"persistencia": persistencia})


@app.post(
    "/agencia/ikki/leads",
    response_model=LeadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar lead B2C/B2B con procedencia y UTM",
)
def registrar_lead(lead: LeadRequest) -> LeadResponse:
    try:
        lead_id = construir_repositorio().guardar_lead(lead)
    except ErrorPersistencia as exc:
        logger.error("Persistencia de lead fallida: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"codigo": "persistencia_error", "mensaje": str(exc)},
        ) from exc

    return LeadResponse(
        lead_id=lead_id,
        estado="guardado",
        embudo=lead.embudo,
        origen_plataforma=lead.origen_plataforma,
    )


@app.post(
    "/api/v1/simular",
    summary="Fee de agencia 15% o simulación legacy",
    description=(
        "Con {presupuesto_base} calcula el fee de agencia del 15%. "
        "Con {cliente_id, rubro, presupuesto_pauta} mantiene el contrato legacy."
    ),
)
def simular_v1(payload: FeeAgenciaRequest | ProspectoLegacy) -> dict:
    """Calcula el fee de agencia o mantiene el contrato histórico."""
    if isinstance(payload, FeeAgenciaRequest):
        fee = motor_fee.calcular_fee_agencia(payload.presupuesto_base_clp)
        return fee.model_dump()

    prospecto = payload
    request = SimulacionRequest(
        cliente_id=prospecto.cliente_id,
        cliente_nombre=prospecto.cliente_id,
        rubro=prospecto.rubro,
        presupuesto_pauta_mensual_clp=prospecto.presupuesto_pauta,
        embudos=[DistribucionEmbudo(embudo="B2C", porcentaje_presupuesto=1.0)],
        persistir=False,
    )
    resultado = motor.simular(request)
    b2c = resultado.embudos[0]

    return {
        "status": "success",
        "campaña_generada": {
            "cliente_id": resultado.cliente_id,
            "nombre": f"Campana_{prospecto.rubro}",
            "presupuesto_total": resultado.presupuesto_total_pauta_clp,
            "fecha_inicio": resultado.fecha_simulacion.isoformat(),
            "configuracion": {
                "fee_calculado": {
                    "pauta_neta": b2c.presupuesto_pauta_mensual_clp,
                    "comision_agencia": b2c.fee.comision_agencia_clp,
                    "fee_fijo": b2c.fee.fee_fijo_asignado_clp,
                    "total_facturar_clp": b2c.fee.total_facturar_clp,
                    "margen_agencia_clp": b2c.fee.margen_agencia_clp,
                },
                "benchmarks_mercado": {
                    "plataforma_recomendada": b2c.canal_principal,
                    "justificacion": b2c.cda.diagnostico,
                    "cpm_promedio_clp": b2c.benchmarks.cpm_clp,
                    "cpc_promedio_clp": b2c.benchmarks.cpc_estimado_clp,
                },
                "proyecciones": {
                    "impresiones_estimadas": b2c.proyecciones.impresiones_estimadas,
                    "clics_estimados": b2c.proyecciones.clics_estimados,
                    "leads_estimados": b2c.proyecciones.leads_estimados,
                },
                "caso_exito": obtener_caso_exito(prospecto.rubro),
                "plan_vuelo": [
                    item.model_dump(mode="json") for item in b2c.plan_30_dias
                ],
                "copys_generados": [
                    item.model_dump(mode="json") for item in b2c.creatividades
                ],
            },
        },
    }
