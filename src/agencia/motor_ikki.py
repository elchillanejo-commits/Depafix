import json
import os
import logging
import random
from datetime import date
from decimal import Decimal
from dotenv import load_dotenv
from supabase import create_client
from src.agencia.prompt_engineer import construir_prompt

load_dotenv()
log = logging.getLogger(__name__)
USE_MOCK_LLM = os.environ.get("IKKI_USE_MOCK", "1") == "1"

class AgenciaIkkiMotor:
    def __init__(self, fee_fijo_clp: int = 150000, pct_pauta: float = 0.15):
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
            res = self.client.table("casos_exito").select("*").ilike("industria", f"%{rubro}%").limit(1).execute()
            return res.data[0] if res.data else {}
        except Exception:
            return {}

    def simular_campana_completa(self, prospecto: dict, presupuesto_pauta: int) -> dict:
        rubro = prospecto.get('rubro', 'general')
        fee = self.calcular_fee_campana(presupuesto_pauta)
        benchmarks = self.obtener_benchmarks(rubro)
        caso_exito = self.obtener_caso_exito(rubro)
        
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
                "copys_generados": [
                    {"titulo": f"Transforma tu experiencia en {rubro}", "cuerpo": "Calidad garantizada y resultados reales.", "cta": "Contáctanos"},
                    {"titulo": f"Líderes en {rubro}", "cuerpo": "Miles de clientes ya confían en nosotros.", "cta": "Ver más"},
                    {"titulo": "Oferta Especial", "cuerpo": "No dejes pasar esta oportunidad única.", "cta": "Cotiza aquí"}
                ]
            }
        }
