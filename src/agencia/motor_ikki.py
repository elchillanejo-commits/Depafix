"""
motor_ikki.py — Motor de cálculo CDA y Copywriting (Agencia Ikki).
Mejorado: Mock varía según el rubro para parecer más real.
ADR01: Portable (Hoy Mock, Diciembre Kimi API).
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

# Plantillas base para el modo MOCK (evita que todos los clientes tengan el mismo texto)
GANCHOS = [
    "¿Cansado de buscar en {rubro} y no encontrar calidad?",
    "Descubre por qué somos los #1 en {rubro}.",
    "Transforma tu experiencia con nuestro servicio premium.",
    "La solución definitiva para tus necesidades de {rubro}.",
    "No pierdas más tiempo ni dinero buscando en {rubro}."
]

CUERPOS = [
    "En {cliente}, entendemos lo que necesitas. Contamos con años de experiencia y los mejores profesionales del rubro.",
    "Aprovecha esta oportunidad única. Calidad garantizada, atención personalizada y resultados que hablan por sí solos.",
    "Miles de clientes ya confían en nosotros. No dejes para mañana lo que puedes resolver hoy con nuestra ayuda.",
    "Ofrecemos un servicio transparente y adaptado a tu presupuesto. Ven y descubre la diferencia.",
    "Tu satisfacción es nuestra prioridad. Contáctanos y recibe una asesoría gratuita por tiempo limitado."
]

CTAS = ["Contáctanos", "Ver más", "Cotiza aquí", "Agenda tu visita", "Solicita info"]

class AgenciaIkkiMotor:
    def __init__(self, fee_fijo_clp: int = 150000, pct_pauta: float = 0.15):
        self.fee_fijo = Decimal(str(fee_fijo_clp))
        self.pct_pauta = Decimal(str(pct_pauta))

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

    def generar_copywriting(self, rubro: str, prospecto_nombre: str) -> list[dict]:
        if USE_MOCK_LLM:
            log.info("Usando Mock de Copywriting mejorado ($0 costo)")
            copys = []
            # Generamos 3 opciones distintas
            for _ in range(3):
                gancho = random.choice(GANCHOS).format(rubro=rubro)
                cuerpo = random.choice(CUERPOS).format(cliente=prospecto_nombre.title())
                cta = random.choice(CTAS)
                copys.append({"titulo": gancho, "cuerpo": cuerpo, "cta": cta})
            return copys

        # (Aquí irá Kimi API en Diciembre)
        return []

    def simular_campana_completa(self, prospecto: dict, presupuesto_pauta: int) -> dict:
        fee = self.calcular_fee_campana(presupuesto_pauta)
        
        if fee["total_facturar_clp"] < 200000:
            recomendacion = "RECHAZAR: Ticket muy bajo."
        else:
            recomendacion = "APROBAR: Campaña rentable."

        copys = self.generar_copywriting(
            rubro=prospecto.get('rubro', 'general'),
            prospecto_nombre=prospecto.get('id', 'demo').replace('_', ' ')
        )

        return {
            "cliente_id": prospecto.get("id", "demo"),
            "nombre": f"Campana_{prospecto.get('rubro', 'general')}",
            "objetivo": "CONVERSIONS",
            "presupuesto_diario": presupuesto_pauta / 30,
            "presupuesto_total": presupuesto_pauta,
            "estado": "BORRADOR",
            "fecha_inicio": date.today().isoformat(),
            "configuracion": {
                "fee_calculado": fee,
                "recomendacion": recomendacion,
                "copys_generados": copys,
                "advertencia": "Borrador generado por IA (Mock). Sujeto a revisión humana."
            }
        }

    def guardar_en_supabase(self, payload: dict) -> bool:
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        try:
            client = create_client(url, key)
            client.table("campanas_meta").insert(payload).execute()
            return True
        except Exception as e:
            log.error(f"Error DB: {e}")
            return False
