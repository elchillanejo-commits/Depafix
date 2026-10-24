"""
repositorio_ikki.py — Persistencia Supabase del módulo Ikki.

La API depende de esta interfaz, no de PostgREST directamente. Si Supabase no
está configurado, la simulación puede ejecutarse en modo dry-run sin tocar red.
"""
from __future__ import annotations

import logging
import os
from typing import Any
from uuid import UUID

from dotenv import load_dotenv
from supabase import create_client

from src.agencia.esquemas import (
    LeadRequest,
    PersistenciaResultado,
    SimulacionResponse,
)

log = logging.getLogger(__name__)


class ErrorPersistencia(RuntimeError):
    """Error controlado de la capa de persistencia."""


class RepositorioIkki:
    def __init__(self, client: Any | None = None) -> None:
        self._client = client
        if self._client is None:
            load_dotenv()
            url = os.environ.get("SUPABASE_URL")
            key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get(
                "SUPABASE_KEY"
            )
            if url and key:
                self._client = create_client(url, key)

    @property
    def disponible(self) -> bool:
        return self._client is not None

    def guardar_simulacion(
        self, simulacion: SimulacionResponse
    ) -> PersistenciaResultado:
        if not self.disponible:
            raise ErrorPersistencia(
                "Supabase no está configurado (SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY)."
            )

        grupo_id = str(simulacion.simulacion_id)
        metadatos_base = {
            **simulacion.metadatos,
            "simulacion_id": grupo_id,
            "cliente_nombre": simulacion.cliente_nombre,
            "modelo_cda": simulacion.modelo_cda,
            "version_modelo": simulacion.supuestos.version_modelo,
        }
        campanas = [
            self._fila_campana(simulacion, embudo, grupo_id, metadatos_base)
            for embudo in simulacion.embudos
        ]
        presupuestos = [
            self._fila_presupuesto(simulacion, embudo, grupo_id, metadatos_base)
            for embudo in simulacion.embudos
        ]

        try:
            respuesta_campanas = (
                self._client.table("campanas_ikki")
                .upsert(campanas, on_conflict="grupo_simulacion_id,embudo")
                .execute()
            )
            respuesta_presupuestos = (
                self._client.table("presupuestos_ikki")
                .upsert(presupuestos, on_conflict="grupo_simulacion_id,embudo")
                .execute()
            )
        except Exception as exc:
            log.exception("Error guardando simulación Ikki en Supabase")
            raise ErrorPersistencia(f"No se pudo persistir la simulación: {exc}") from exc

        ids = [
            str(fila["id"])
            for fila in [*(respuesta_campanas.data or []), *(respuesta_presupuestos.data or [])]
            if fila.get("id")
        ]
        return PersistenciaResultado(
            solicitada=True,
            estado="guardada",
            motivo="Upsert idempotente por (grupo_simulacion_id, embudo).",
            campanas_guardadas=len(respuesta_campanas.data or campanas),
            presupuestos_guardados=len(respuesta_presupuestos.data or presupuestos),
            ids=ids,
        )

    def guardar_lead(self, lead: LeadRequest) -> UUID:
        if not self.disponible:
            raise ErrorPersistencia(
                "Supabase no está configurado (SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY)."
            )

        fila = lead.model_dump(mode="json")
        fila["fuente"] = lead.origen_plataforma
        fila["utm"] = {
            clave: valor
            for clave, valor in {
                "source": lead.utm_source,
                "medium": lead.utm_medium,
                "campaign": lead.utm_campaign,
                "content": lead.utm_content,
                "term": lead.utm_term,
            }.items()
            if valor is not None
        }

        try:
            consulta = self._client.table("leads_ikki")
            if lead.idempotency_key:
                respuesta = consulta.upsert(
                    fila, on_conflict="idempotency_key"
                ).execute()
            else:
                respuesta = consulta.insert(fila).execute()
        except Exception as exc:
            log.exception("Error guardando lead Ikki en Supabase")
            raise ErrorPersistencia(f"No se pudo guardar el lead: {exc}") from exc

        if not respuesta.data:
            raise ErrorPersistencia("Supabase no devolvió el lead insertado.")
        return UUID(str(respuesta.data[0]["id"]))

    @staticmethod
    def _fila_campana(
        simulacion: SimulacionResponse,
        embudo: Any,
        grupo_id: str,
        metadatos: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "grupo_simulacion_id": grupo_id,
            "cliente_id": simulacion.cliente_id,
            "nombre": embudo.nombre,
            "rubro": simulacion.rubro,
            "plataforma": embudo.benchmarks.plataforma_codigo,
            "estado": "simulada",
            "estructura_cda": embudo.cda.model_dump(mode="json"),
            "presupuesto_pauta_clp": embudo.presupuesto_pauta_mensual_clp,
            "fee_fijo_clp": embudo.fee.fee_fijo_asignado_clp,
            "pct_pauta": simulacion.fee.pct_pauta,
            "comision_agencia_clp": embudo.fee.comision_agencia_clp,
            "total_facturar_clp": embudo.fee.total_facturar_clp,
            "margen_agencia_clp": embudo.fee.margen_agencia_clp,
            "proyecciones": embudo.proyecciones.model_dump(mode="json"),
            "benchmarks": embudo.benchmarks.model_dump(mode="json"),
            "plan_vuelo": [
                item.model_dump(mode="json") for item in embudo.plan_30_dias
            ],
            "copys": [
                item.model_dump(mode="json") for item in embudo.creatividades
            ],
            "metadatos": metadatos,
            "fecha_inicio": simulacion.fecha_simulacion.isoformat(),
            "fecha_fin": None,
            "embudo": embudo.embudo,
            "objetivo": embudo.objetivo,
            "publico_objetivo": embudo.publico_objetivo,
            "canal_principal": embudo.canal_principal,
            "canales_secundarios": embudo.canales_secundarios,
            "periodo_mes": simulacion.periodo_mes.isoformat(),
            "kpis_objetivo": embudo.cda.accion.kpis,
        }

    @staticmethod
    def _fila_presupuesto(
        simulacion: SimulacionResponse,
        embudo: Any,
        grupo_id: str,
        metadatos: dict[str, Any],
    ) -> dict[str, Any]:
        kpis = embudo.cda.accion.kpis
        leads_objetivo = int(
            kpis.get("leads_objetivo_mes", kpis.get("demos_objetivo_mes", 0))
        )
        return {
            "grupo_simulacion_id": grupo_id,
            "cliente_id": simulacion.cliente_id,
            "periodo_mes": simulacion.periodo_mes.isoformat(),
            "embudo": embudo.embudo,
            "presupuesto_pauta_clp": embudo.presupuesto_pauta_mensual_clp,
            "fee_fijo_clp": embudo.fee.fee_fijo_asignado_clp,
            "pct_pauta": simulacion.fee.pct_pauta,
            "comision_agencia_clp": embudo.fee.comision_agencia_clp,
            "total_facturar_clp": embudo.fee.total_facturar_clp,
            "margen_agencia_clp": embudo.fee.margen_agencia_clp,
            "gasto_real_clp": 0,
            "leads_objetivo": leads_objetivo,
            "estado": "simulado",
            "metadatos": metadatos,
        }
