"""
motor_cda.py — Motor de simulación CDA para Ikki.

El cálculo de economía, proyecciones y playbooks es determinístico. Las
creatividades se generan con RAG + LLM cuando están habilitados; si fallan,
se usan las plantillas fijas de cda.py para no romper la API.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from uuid import uuid4

from src.agencia.benchmarks import (
    FUENTE_BENCHMARKS,
    NOTA_SUPUESTOS,
    BenchmarkEmbudo,
    obtener_benchmark,
)
from src.agencia.cda import (
    construir_cda,
    creatividades,
    plan_30_dias,
    reglas_cumplimiento,
)
from src.agencia.esquemas import (
    BenchmarkResponse,
    Creatividad,
    Embudo,
    EmbudoResultado,
    FeeEmbudo,
    FeeGlobal,
    PersistenciaResultado,
    ProyeccionesEmbudo,
    ResumenGlobal,
    SimulacionRequest,
    SimulacionResponse,
    SupuestosSimulacion,
)
from src.agencia.prompt_engineer import construir_prompt
from src.agencia.rag import obtener_contexto_relevante

log = logging.getLogger(__name__)

VERSION_MODELO = "1.0.0"
MODELO_CDA = "Contexto-Diagnóstico-Acción"

USE_MOCK_LLM = os.environ.get("IKKI_USE_MOCK", "1") == "1"
LLM_MODEL = os.environ.get("IKKI_LLM_MODEL", "claude-haiku-5-5")


def _copys_desde_llm(
    rubro: str, cliente: str, embudo: Embudo, contexto_rag: str
) -> list[dict]:
    """Una llamada al LLM por embudo; devuelve copys con titulo/cuerpo/cta."""
    import anthropic

    mensajes = construir_prompt(
        f"{rubro} (embudo {embudo})", cliente, contexto_rag, n_anuncios=3
    )
    respuesta = anthropic.Anthropic(
        api_key=os.environ["ANTHROPIC_API_KEY"]
    ).messages.create(
        model=LLM_MODEL,
        max_tokens=1024,
        system=mensajes[0]["content"],
        messages=[{"role": "user", "content": mensajes[1]["content"]}],
    )
    texto = "".join(
        bloque.text for bloque in respuesta.content if bloque.type == "text"
    ).strip()
    inicio, fin = texto.find("["), texto.rfind("]")
    if inicio == -1 or fin < inicio:
        raise ValueError("El LLM no devolvió un arreglo JSON")

    copys = json.loads(texto[inicio : fin + 1])
    if not isinstance(copys, list):
        raise ValueError("El LLM no devolvió una lista de copys")

    limpios = []
    for copia in copys:
        if not isinstance(copia, dict):
            continue
        valores = {
            clave: str(copia.get(clave, "")).strip()
            for clave in ("titulo", "cuerpo", "cta")
        }
        if all(valores.values()):
            limpios.append(valores)
    if not limpios:
        raise ValueError("El LLM no devolvió copys válidos")
    return limpios


def _creatividades_con_rag_y_llm(
    rubro: str, cliente: str, embudo: Embudo, plantillas: list[Creatividad]
) -> list[Creatividad]:
    """Reemplaza titulo/cuerpo/cta de las plantillas manteniendo su formato."""
    if USE_MOCK_LLM or not os.environ.get("ANTHROPIC_API_KEY"):
        return plantillas

    try:
        contexto_rag = obtener_contexto_relevante(
            f"anuncios de alta conversión para el rubro {rubro} en el embudo {embudo}"
        )
        if not contexto_rag:
            return plantillas

        copys = _copys_desde_llm(rubro, cliente, embudo, contexto_rag)
        generadas = []
        for indice, plantilla in enumerate(plantillas):
            if indice < len(copys):
                generadas.append(
                    plantilla.model_copy(update=copys[indice])
                )
            else:
                generadas.append(plantilla)
        log.info("Creatividades %s generadas con RAG+LLM para %s", embudo, rubro)
        return generadas
    except Exception:
        log.exception(
            "RAG/LLM fallaron para %s (%s); se usan plantillas fijas",
            rubro,
            embudo,
        )
        return plantillas


def _redondear(valor: Decimal) -> int:
    return int(valor.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _porcentaje(monto: int, pct: float) -> int:
    return _redondear(Decimal(monto) * Decimal(str(pct)))


def _pct(valor: Decimal) -> float:
    return float((valor * 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _repartir(total: int, participaciones: list[float]) -> list[int]:
    """Reparte un entero sin perder ni inventar pesos por redondeo."""
    if total < 0:
        raise ValueError("El monto a repartir no puede ser negativo.")
    if not participaciones:
        raise ValueError("Se requiere al menos una participación.")
    if abs(sum(participaciones) - 1.0) > 1e-4:
        raise ValueError("Las participaciones deben sumar 1.0.")

    montos: list[int] = []
    acumulado = 0
    for indice, participacion in enumerate(participaciones):
        if indice == len(participaciones) - 1:
            monto = total - acumulado
        else:
            monto = _redondear(Decimal(total) * Decimal(str(participacion)))
            acumulado += monto
        montos.append(monto)

    if any(monto < 0 for monto in montos):
        raise ValueError("El reparto generó un monto negativo.")
    return montos


def _proyectar(
    embudo: Embudo,
    benchmark: BenchmarkEmbudo,
    presupuesto_mensual_clp: int,
    horizonte_dias: int,
) -> tuple[ProyeccionesEmbudo, int]:
    pauta_simulada = _redondear(
        Decimal(presupuesto_mensual_clp) * Decimal(horizonte_dias) / Decimal(30)
    )
    pauta = Decimal(pauta_simulada)
    impresiones = int(pauta / Decimal(benchmark.cpm_clp) * Decimal(1000))
    clics = int(Decimal(impresiones) * benchmark.ctr)
    leads = int(Decimal(clics) * benchmark.tasa_conversion_lead)
    clientes = int(Decimal(leads) * benchmark.tasa_cierre)
    ingresos = clientes * benchmark.ticket_promedio_clp

    cpc = _redondear(pauta / Decimal(clics)) if clics > 0 else 0
    cpl = _redondear(pauta / Decimal(leads)) if leads > 0 else None
    cac = _redondear(pauta / Decimal(clientes)) if clientes > 0 else None
    roas = (
        float((Decimal(ingresos) / pauta).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
        if pauta > 0
        else None
    )

    return (
        ProyeccionesEmbudo(
            pauta_simulada_clp=pauta_simulada,
            impresiones_estimadas=impresiones,
            clics_estimados=clics,
            leads_estimados=leads,
            clientes_estimados=clientes,
            cpl_clp=cpl,
            cac_clp=cac,
            ingresos_estimados_clp=ingresos,
            roas_estimado=roas,
            tasa_clics_pct=_pct(benchmark.ctr),
            tasa_conversion_lead_pct=_pct(benchmark.tasa_conversion_lead),
            tasa_cierre_pct=_pct(benchmark.tasa_cierre),
        ),
        cpc,
    )


class MotorCDA:
    """Motor de simulación; RAG/LLM son opcionales y tienen fallback local."""

    def simular(self, request: SimulacionRequest) -> SimulacionResponse:
        fecha = date.today()
        periodo_mes = fecha.replace(day=1)
        simulacion_id = uuid4()

        participaciones = [
            item.porcentaje_presupuesto for item in request.embudos
        ]
        presupuestos = _repartir(
            request.presupuesto_pauta_mensual_clp, participaciones
        )
        fees_asignados = _repartir(request.fee_fijo_clp, participaciones)

        embudos: list[EmbudoResultado] = []
        for distribucion, presupuesto, fee_asignado in zip(
            request.embudos, presupuestos, fees_asignados
        ):
            benchmark = obtener_benchmark(distribucion.embudo)
            proyecciones, cpc = _proyectar(
                distribucion.embudo,
                benchmark,
                presupuesto,
                request.horizonte_dias,
            )
            comision = _porcentaje(presupuesto, request.pct_pauta)
            cda = construir_cda(distribucion.embudo, benchmark)
            creatividades_embudo = _creatividades_con_rag_y_llm(
                request.rubro,
                request.cliente_nombre,
                distribucion.embudo,
                creatividades(distribucion.embudo),
            )

            embudos.append(
                EmbudoResultado(
                    embudo=distribucion.embudo,
                    nombre=f"Ikki {distribucion.embudo} — {request.cliente_nombre}",
                    objetivo=distribucion.objetivo or benchmark.objetivo,
                    publico_objetivo=(
                        distribucion.publico_objetivo or benchmark.publico_objetivo
                    ),
                    participacion_pct=round(
                        distribucion.porcentaje_presupuesto * 100, 2
                    ),
                    presupuesto_pauta_mensual_clp=presupuesto,
                    presupuesto_diario_clp=_redondear(
                        Decimal(presupuesto) / Decimal(30)
                    ),
                    canal_principal=benchmark.canal_principal,
                    canales_secundarios=list(benchmark.canales_secundarios),
                    cda=cda,
                    benchmarks=BenchmarkResponse(
                        plataforma_codigo=benchmark.plataforma_codigo,
                        canal_principal=benchmark.canal_principal,
                        canales_secundarios=list(benchmark.canales_secundarios),
                        cpm_clp=benchmark.cpm_clp,
                        cpc_estimado_clp=cpc,
                        ctr_pct=_pct(benchmark.ctr),
                        tasa_conversion_lead_pct=_pct(
                            benchmark.tasa_conversion_lead
                        ),
                        tasa_cierre_pct=_pct(benchmark.tasa_cierre),
                        ticket_promedio_clp=benchmark.ticket_promedio_clp,
                        fuente=benchmark.fuente,
                    ),
                    proyecciones=proyecciones,
                    fee=FeeEmbudo(
                        fee_fijo_asignado_clp=fee_asignado,
                        comision_agencia_clp=comision,
                        total_facturar_clp=presupuesto + fee_asignado + comision,
                        margen_agencia_clp=fee_asignado + comision,
                    ),
                    plan_30_dias=plan_30_dias(distribucion.embudo),
                    creatividades=creatividades_embudo,
                    cumplimiento=reglas_cumplimiento(distribucion.embudo),
                )
            )

        comision_total = sum(item.fee.comision_agencia_clp for item in embudos)
        fee_total = request.fee_fijo_clp
        margen_total = fee_total + comision_total
        pauta_simulada = sum(
            item.proyecciones.pauta_simulada_clp for item in embudos
        )
        leads_total = sum(item.proyecciones.leads_estimados for item in embudos)
        clientes_total = sum(
            item.proyecciones.clientes_estimados for item in embudos
        )
        ingresos_total = sum(
            item.proyecciones.ingresos_estimados_clp for item in embudos
        )

        resumen = ResumenGlobal(
            presupuesto_total_pauta_clp=request.presupuesto_pauta_mensual_clp,
            pauta_simulada_clp=pauta_simulada,
            impresiones_estimadas=sum(
                item.proyecciones.impresiones_estimadas for item in embudos
            ),
            clics_estimados=sum(
                item.proyecciones.clics_estimados for item in embudos
            ),
            leads_estimados=leads_total,
            clientes_estimados=clientes_total,
            cpl_promedio_clp=(
                _redondear(Decimal(pauta_simulada) / Decimal(leads_total))
                if leads_total > 0
                else None
            ),
            cac_promedio_clp=(
                _redondear(Decimal(pauta_simulada) / Decimal(clientes_total))
                if clientes_total > 0
                else None
            ),
            ingresos_estimados_clp=ingresos_total,
            roas_estimado=(
                float(
                    (Decimal(ingresos_total) / Decimal(pauta_simulada)).quantize(
                        Decimal("0.01"), rounding=ROUND_HALF_UP
                    )
                )
                if pauta_simulada > 0
                else None
            ),
            leads_por_embudo={
                item.embudo: item.proyecciones.leads_estimados for item in embudos
            },
            clientes_por_embudo={
                item.embudo: item.proyecciones.clientes_estimados for item in embudos
            },
        )

        persistencia = PersistenciaResultado(
            solicitada=request.persistir,
            estado="omitida",
            motivo=(
                "Pendiente de persistencia en Supabase."
                if request.persistir
                else "persistir=false: simulación dry-run, sin escritura en Supabase."
            ),
        )

        return SimulacionResponse(
            simulacion_id=simulacion_id,
            cliente_id=request.cliente_id,
            cliente_nombre=request.cliente_nombre,
            rubro=request.rubro,
            fecha_simulacion=fecha,
            periodo_mes=periodo_mes,
            horizonte_dias=request.horizonte_dias,
            moneda=request.moneda,
            modelo_cda=MODELO_CDA,
            presupuesto_total_pauta_clp=request.presupuesto_pauta_mensual_clp,
            fee=FeeGlobal(
                fee_fijo_clp=fee_total,
                pct_pauta=request.pct_pauta,
                comision_agencia_clp=comision_total,
                total_facturar_clp=(
                    request.presupuesto_pauta_mensual_clp + fee_total + comision_total
                ),
                margen_agencia_clp=margen_total,
            ),
            embudos=embudos,
            resumen=resumen,
            supuestos=SupuestosSimulacion(
                fuente_benchmarks=FUENTE_BENCHMARKS,
                nota=NOTA_SUPUESTOS,
                horizonte_dias=request.horizonte_dias,
                modelo_atribucion=(
                    "Lead declarado + último clic; sin ventana de atribución multitoque."
                ),
                moneda=request.moneda,
                version_modelo=VERSION_MODELO,
            ),
            metadatos=request.metadatos,
            persistencia=persistencia,
        )
