"""
meta_ads_integrator.py — Integración con Meta Marketing API (Sandbox).
Prepara la estructura para crear campañas reales en el futuro.
"""
import json
import logging
import os

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

class MetaAdsIntegrator:
    def __init__(self, access_token: str = None, ad_account_id: str = None):
        # En el futuro, se pasarán las credenciales desde el entorno o Supabase
        self.access_token = access_token or os.environ.get("META_ACCESS_TOKEN", "TOKEN_SIMULADO")
        self.ad_account_id = ad_account_id or os.environ.get("META_AD_ACCOUNT_ID", "act_123456789")
        log.info(f"Integrador Meta Ads inicializado para la cuenta: {self.ad_account_id}")

    def crear_campana_sandbox(self, payload_ikki: dict) -> dict:
        """Simula la creación de una campaña en Meta Ads (Sandbox)."""
        log.info("--- CREANDO CAMPAÑA EN META ADS (MODO SANDBOX) ---")
        
        # Mapeo de datos de nuestro motor a lo que pide Meta
        nombre = payload_ikki.get("nombre", "Campaña Ikki Sandbox")
        presupuesto_diario = payload_ikki.get("presupuesto_diario", 10000)
        objetivo = "OUTCOME_LEADS" # Objetivo recomendado para 2026
        
        # Meta pide el presupuesto en centavos (ej. $10.000 CLP -> 1000000)
        presupuesto_centavos = int(presupuesto_diario * 100)
        
        log.info(f"Nombre: {nombre}")
        log.info(f"Objetivo: {objetivo}")
        log.info(f"Presupuesto Diario: ${presupuesto_diario} CLP (Meta: {presupuesto_centavos} centavos)")

        # --- CÓDIGO REAL (COMENTADO) PARA CUANDO TENGAMOS CREDENCIALES ---
        # from facebook_business.api import FacebookAdsApi
        # from facebook_business.adobjects.campaign import Campaign
        # FacebookAdsApi.init(access_token=self.access_token)
        # campaign = Campaign(parent_id=self.ad_account_id)
        # campaign.update({
        #     Campaign.Field.name: nombre,
        #     Campaign.Field.objective: objetivo,
        #     Campaign.Field.status: Campaign.Status.paused,
        #     Campaign.Field.daily_budget: presupuesto_centavos,
        # })
        # campaign.remote_create()
        # return {"campaign_id": campaign['id'], "status": "PAUSED"}

        # Simulación de respuesta
        return {
            "campaign_id": "23842342-SANDBOX",
            "status": "PAUSED",
            "mensaje": "Campaña creada en Sandbox. Revisa en el Administrador de Anuncios.",
            "detalles": {
                "nombre": nombre,
                "objetivo": objetivo,
                "presupuesto_centavos": presupuesto_centavos
            }
        }

if __name__ == "__main__":
    # Payload de ejemplo (así lo genera tu motor_ikki.py)
    payload_ejemplo = {
        "nombre": "Campana_inmobiliaria",
        "presupuesto_diario": 16666.66,
        "configuracion": {
            "briefing_estrategia": {
                "publico_objetivo_sugerido": "Hombres y mujeres, 30-55 años, Providencia",
                "creatividades_recomendadas": ["Video Testimonio", "Imagen Estática"]
            }
        }
    }
    
    integrador = MetaAdsIntegrator()
    respuesta = integrador.crear_campana_sandbox(payload_ejemplo)
    print(json.dumps(respuesta, indent=2, ensure_ascii=False))
