import os
import json
import logging
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Literal

from dotenv import load_dotenv
from pydantic import AliasChoices, BaseModel, ConfigDict, Field
from supabase import create_client

from src.agencia.prompt_engineer import construir_prompt
from src.agencia.rag import obtener_contexto_relevante as buscar_contexto_rag

load_dotenv()
log = logging.getLogger(__name__)
USE_MOCK_LLM = os.environ.get("IKKI_USE_MOCK", "1") == "1"
LLM_MODEL = os.environ.get("IKKI_LLM_MODEL", "claude-haiku-5-5")


class FeeAgenciaRequest(BaseModel):
    """Presupuesto base para el cálculo del fee de agencia."""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    presupuesto_base_clp: int = Field(
        gt=0,
        validation_alias=AliasChoices("presupuesto_base_clp", "presupuesto_base"),
        description="Presupuesto base de pauta en CLP.",
    )


class FeeAgenciaResponse(BaseModel):
    """Resultado del fee de agencia sobre el presupuesto base."""

    status: Literal["success"] = "success"
    presupuesto_base_clp: int
    pct_fee_agencia: float
    fee_agencia_clp: int
    total_cliente_clp: int
    moneda: Literal["CLP"] = "CLP"


class MotorIkki:
    """Cálculo puro del fee de agencia (sin dependencias de Supabase)."""

    def __init__(self, pct_fee_agencia: float = 0.15):
        if not 0 <= pct_fee_agencia <= 1:
            raise ValueError("pct_fee_agencia debe estar entre 0 y 1.")
        self.pct_fee_agencia = Decimal(str(pct_fee_agencia))

    def calcular_fee_agencia(self, presupuesto_base_clp: int) -> FeeAgenciaResponse:
        if presupuesto_base_clp <= 0:
            raise ValueError("presupuesto_base_clp debe ser mayor que cero.")
        base = Decimal(str(presupuesto_base_clp))
        fee = (base * self.pct_fee_agencia).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP
        )
        return FeeAgenciaResponse(
            presupuesto_base_clp=int(base),
            pct_fee_agencia=float(self.pct_fee_agencia),
            fee_agencia_clp=int(fee),
            total_cliente_clp=int(base + fee),
        )


class AgenciaIkkiMotor(MotorIkki):
    def __init__(self, fee_fijo_clp: int = 150000, pct_pauta: float = 0.15):
        super().__init__(pct_fee_agencia=pct_pauta)
        self.fee_fijo = Decimal(str(fee_fijo_clp))
        self.pct_pauta = Decimal(str(pct_pauta))
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        self.client = create_client(url, key) if url and key else None

    def calcular_fee_campana(self, presupuesto_pauta_clp: int) -> dict:
        pauta = Decimal(str(presupuesto_pauta_clp))
        comision = pauta * self.pct_pauta
        total_cliente = self.fee_fijo + pauta + comision
        return {
            "pauta_neta": int(pauta),
            "comision_agencia": int(comision),
            "fee_fijo": int(self.fee_fijo),
            "total_facturar_clp": int(total_cliente),
            "margen_agencia_clp": int(self.fee_fijo + comision)
        }

    def obtener_benchmarks(self, rubro: str) -> dict:
        if not self.client: return {}
        try:
            matriz = self.client.table("matriz_plataforma").select("*").ilike("rubro", f"%{rubro}%").execute().data
            red = matriz[0]["red_principal"] if matriz else "Meta"
            just = matriz[0]["justificacion"] if matriz else "Estrategia estándar."
            bench = self.client.table("benchmarks_ads").select("*").ilike("industria", f"%{rubro}%").execute().data
            cpm = (bench[0]["cpm_min_clp"] + bench[0]["cpm_max_clp"]) / 2 if bench else 5000
            cpc = (bench[0]["cpc_min_clp"] + bench[0]["cpc_max_clp"]) / 2 if bench else 250
            return {"plataforma_recomendada": red, "justificacion": just, "cpm_promedio_clp": int(cpm), "cpc_promedio_clp": int(cpc)}
        except Exception:
            return {"plataforma_recomendada": "Meta", "justificacion": "Estrategia estándar.", "cpm_promedio_clp": 5000, "cpc_promedio_clp": 250}

    def obtener_caso_exito(self, rubro: str) -> dict:
        if not self.client: return {}
        try:
            # Solo casos reales: las estimaciones de mercado nunca se muestran como caso de éxito.
            res = self.client.table("casos_exito").select("*").ilike("industria", f"%{rubro}%").eq("tipo", "real").order("id").limit(1).execute()
            return res.data[0] if res.data else {}
        except Exception:
            return {}

    def obtener_contexto_relevante(self, rubro: str, k: int = 3, categoria: str | None = None) -> str:
        """Conocimiento de Meta/Google Ads desde Supabase (pgvector). "" si el RAG no está disponible."""
        try:
            return buscar_contexto_rag(f"anuncios de alta conversión para el rubro {rubro}", k, categoria)
        except Exception:
            log.exception("RAG no disponible; se sigue sin contexto")
            return ""

    @staticmethod
    def _copys_fijos(rubro: str) -> list[dict]:
        return [
            {"titulo": f"Transforma tu experiencia en {rubro}", "cuerpo": "Calidad garantizada y resultados reales.", "cta": "Contáctanos"},
            {"titulo": f"Líderes en {rubro}", "cuerpo": "Miles de clientes ya confían en nosotros.", "cta": "Ver más"},
            {"titulo": "Oferta Especial", "cuerpo": "No dejes pasar esta oportunidad única.", "cta": "Cotiza aquí"}
        ]

    def generar_copys(self, rubro: str, cliente: str, contexto_rag: str) -> tuple[list[dict], str]:
        """Copys vía LLM con el contexto RAG. Devuelve (copys, origen); cae a copys fijos si no hay LLM."""
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if USE_MOCK_LLM or not api_key or not contexto_rag:
            return self._copys_fijos(rubro), "fijo"
        try:
            import anthropic
            mensajes = construir_prompt(rubro, cliente, contexto_rag, n_anuncios=3)
            respuesta = anthropic.Anthropic(api_key=api_key).messages.create(
                model=LLM_MODEL,
                max_tokens=1024,
                system=mensajes[0]["content"],
                messages=[{"role": "user", "content": mensajes[1]["content"]}],
            )
            texto = "".join(b.text for b in respuesta.content if b.type == "text").strip()
            copys = json.loads(texto[texto.find("["):texto.rfind("]") + 1])
            copys = [{k: str(c[k]) for k in ("titulo", "cuerpo", "cta")} for c in copys if isinstance(c, dict)]
            if not copys:
                raise ValueError("El LLM no devolvió copys válidos")
            return copys[:3], "llm"
        except Exception:
            log.exception("Fallo generando copys con LLM; se usan copys fijos")
            return self._copys_fijos(rubro), "fijo"

    def simular_campana_completa(self, prospecto: dict, presupuesto_pauta: int) -> dict:
        rubro = prospecto.get('rubro', 'general')
        fee = self.calcular_fee_campana(presupuesto_pauta)
        benchmarks = self.obtener_benchmarks(rubro)
        caso_exito = self.obtener_caso_exito(rubro)
        contexto_rag = self.obtener_contexto_relevante(rubro)
        copys, origen_copys = self.generar_copys(rubro, prospecto.get("nombre", rubro), contexto_rag)
        
        proyecciones = {}
        if benchmarks.get("cpm_promedio_clp"):
            impresiones = int((presupuesto_pauta / benchmarks["cpm_promedio_clp"]) * 1000)
            clics = int(impresiones * 0.01)
            proyecciones = {"impresiones_estimadas": impresiones, "clics_estimados": clics}

        # Plan de Vuelo (Semana 1 a 4)
        plan_vuelo = [
            {"semana": "Semana 1", "accion": "Configuración de Píxel y Lanzamiento de Campaña."},
            {"semana": "Semana 2", "accion": "Testeo A/B de Creatividades (Video vs Imagen)."},
            {"semana": "Semana 3", "accion": "Optimización de Presupuesto (escalar lo que funciona)."},
            {"semana": "Semana 4", "accion": "Reporte de Resultados y Ajuste de Estrategia."}
        ]

        return {
            "cliente_id": prospecto.get("id", "demo"),
            "nombre": f"Campana_{rubro}",
            "presupuesto_total": presupuesto_pauta,
            "fecha_inicio": date.today().isoformat(),
            "configuracion": {
                "fee_calculado": fee,
                "benchmarks_mercado": benchmarks,
                "proyecciones": proyecciones,
                "caso_exito": caso_exito,
                "plan_vuelo": plan_vuelo,
                "copys_generados": copys,
                "origen_copys": origen_copys,
                "contexto_rag_usado": bool(contexto_rag),
            }
        }
