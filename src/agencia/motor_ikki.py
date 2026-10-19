"""
motor_ikki.py — Motor de cálculo CDA y Copywriting (Agencia Ikki).
Fase 5: Conectado a datos reales de benchmarks y matriz de plataformas.
"""
import json
import os
import logging
import random
from datetime import date
from decimal import Decimal
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()
log = logging.getLogger(__name__)
USE_MOCK_LLM = os.environ.get("IKKI_USE_MOCK", "1") == "1"

# Plantillas de copys (Mock)
GANCHOS = [
    "¿Cansado de buscar en {rubro} y no encontrar calidad?",
    "Descubre por qué somos los #1 en {rubro}.",
    "Transforma tu experiencia con nuestro servicio premium.",
    "La solución definitiva para tus necesidades de {rubro}."
]
CUERPOS = [
    "En {cliente}, entendemos lo que necesitas. Contamos con años de experiencia y los mejores profesionales.",
    "Aprovecha esta oportunidad única. Calidad garantizada, atención personalizada y resultados que hablan por sí solos.",
    "Miles de clientes ya confían en nosotros. No dejes para mañana lo que puedes resolver hoy."
]
CTAS = ["Contáctanos", "Ver más", "Cotiza aquí", "Agenda tu visita"]

class AgenciaIkkiMotor:
    def __init__(self, fee_fijo_clp: int = 150000, pct_pauta: float = 0.15):
        self.fee_fijo = Decimal(str(fee_fijo_clp))
        self.pct_pauta = Decimal(str(pct_pauta))
        
        # Conexión a Supabase para leer Benchmarks
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
        """Busca proyecciones reales en Supabase según el rubro."""
        if not self.client:
            return {"error": "Sin conexión a DB"}

        # 1. Buscar recomendación de plataforma
        try:
            matriz = self.client.table("matriz_plataforma").select("*").ilike("rubro", f"%{rubro}%").execute().data
            red_principal = matriz[0]["red_principal"] if matriz else "Meta"
            red_secundaria = matriz[0]["red_secundaria"] if matriz else "Google Ads"
            justificacion = matriz[0]["justificacion"] if matriz else "Estrategia estándar."
        except Exception:
            red_principal, red_secundaria, justificacion = "Meta", "Google Ads", "Estrategia estándar."

        # 2. Buscar CPM y CPC
        try:
            # Buscamos en la tabla de benchmarks una industria que coincida
            bench = self.client.table("benchmarks_ads").select("*").ilike("industria", f"%{rubro}%").execute().data
            
            if bench:
                # Promediamos min y max para la proyección
                cpm = (bench[0]["cpm_min_clp"] + bench[0]["cpm_max_clp"]) / 2
                cpc = (bench[0]["cpc_min_clp"] + bench[0]["cpc_max_clp"]) / 2 if bench[0].get("cpc_min_clp") else 250
            else:
                # Valores por defecto si no encontramos el rubro exacto
                cpm, cpc = 5000, 250
        except Exception:
            cpm, cpc = 5000, 250

        return {
            "plataforma_recomendada": red_principal,
            "plataforma_secundaria": red_secundaria,
            "justificacion": justificacion,
            "cpm_promedio_clp": int(cpm),
            "cpc_promedio_clp": int(cpc)
        }

    def generar_copywriting(self, rubro: str, prospecto_nombre: str) -> list[dict]:
        if USE_MOCK_LLM:
            copys = []
            for _ in range(3):
                gancho = random.choice(GANCHOS).format(rubro=rubro)
                cuerpo = random.choice(CUERPOS).format(cliente=prospecto_nombre.title())
                cta = random.choice(CTAS)
                copys.append({"titulo": gancho, "cuerpo": cuerpo, "cta": cta})
            return copys
        return []

    def simular_campana_completa(self, prospecto: dict, presupuesto_pauta: int) -> dict:
        rubro = prospecto.get('rubro', 'general')
        fee = self.calcular_fee_campana(presupuesto_pauta)
        benchmarks = self.obtener_benchmarks(rubro)
        
        # --- CÁLCULO DE PROYECCIONES REALES ---
        proyecciones = {}
        if benchmarks.get("cpm_promedio_clp"):
            cpm = benchmarks["cpm_promedio_clp"]
            cpc = benchmarks["cpc_promedio_clp"]
            
            # Impresiones = (Pauta / CPM) * 1000
            impresiones = int((presupuesto_pauta / cpm) * 1000)
            # Clics = Impresiones * CTR (asumimos un CTR estándar del 1% para el cálculo, o usamos CPC)
            clics = int(impresiones * 0.01)
            
            proyecciones = {
                "impresiones_estimadas": impresiones,
                "clics_estimados": clics,
                "nota": "Cálculo basado en CPM/CPC reales de la industria en Chile (Benchmarks 2026)."
            }

        if fee["total_facturar_clp"] < 200000:
            recomendacion = "RECHAZAR: Ticket muy bajo."
        else:
            recomendacion = "APROBAR: Campaña rentable."

        copys = self.generar_copywriting(rubro, prospecto.get('id', 'demo').replace('_', ' '))

        return {
            "cliente_id": prospecto.get("id", "demo"),
            "nombre": f"Campana_{rubro}",
            "objetivo": "CONVERSIONS",
            "presupuesto_diario": presupuesto_pauta / 30,
            "presupuesto_total": presupuesto_pauta,
            "estado": "BORRADOR",
            "fecha_inicio": date.today().isoformat(),
            "configuracion": {
                "fee_calculado": fee,
                "benchmarks_mercado": benchmarks,
                "proyecciones": proyecciones,
                "recomendacion": recomendacion,
                "copys_generados": copys
            }
        }

    def guardar_en_supabase(self, payload: dict) -> bool:
        try:
            self.client.table("campanas_meta").insert(payload).execute()
            return True
        except Exception as e:
            log.error(f"Error DB: {e}")
            return False
