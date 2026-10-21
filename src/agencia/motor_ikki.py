"""
motor_ikki.py — Motor de cálculo CDA y Copywriting (Agencia Ikki).
Fase 8: Integración del Prompt Engineer con el RAG (Buscador de 347 KB).
"""
import json
import os
import logging
import random
from datetime import date
from decimal import Decimal
from dotenv import load_dotenv
from supabase import create_client
# Importamos el estructurador de prompts
from src.agencia.prompt_engineer import construir_prompt

load_dotenv()
log = logging.getLogger(__name__)
USE_MOCK_LLM = os.environ.get("IKKI_USE_MOCK", "1") == "1"

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

    @staticmethod
    def _primer_valor(fila: dict, claves: tuple):
        for clave in claves:
            valor = fila.get(clave)
            if valor not in (None, "", [], {}):
                return valor
        return None

    def _consultar_por_plataforma(self, tabla: str, plataforma: str) -> list[dict]:
        if not self.client or not plataforma:
            return []
        try:
            filas = (
                self.client.table(tabla)
                .select("*")
                .ilike("plataforma", f"%{plataforma}%")
                .execute()
                .data
            )
            return filas or []
        except Exception as error:
            log.debug(f"Filtro por plataforma no disponible en {tabla}: {error}")

        try:
            return self.client.table(tabla).select("*").execute().data or []
        except Exception as error:
            log.warning(f"No se pudo consultar la tabla {tabla}: {error}")
            return []

    @staticmethod
    def _texto_regla(fila: dict) -> str:
        if not isinstance(fila, dict):
            return ""
        for clave in ("regla", "regla_de_oro", "descripcion", "contenido", "texto", "insight"):
            valor = fila.get(clave)
            if valor not in (None, "", [], {}):
                return str(valor).strip()
        return ""

    def _normalizar_cotizacion(self, fila: dict) -> dict:
        if not isinstance(fila, dict):
            return {}
        tipo = self._primer_valor(
            fila, ("tipo", "tipo_servicio", "servicio", "plan", "paquete", "categoria")
        )
        minimo = self._primer_valor(
            fila, ("min", "precio_min", "precio_min_clp", "precio_clp_min", "min_clp")
        )
        maximo = self._primer_valor(
            fila, ("max", "precio_max", "precio_max_clp", "precio_clp_max", "max_clp")
        )
        if minimo is None and maximo is None:
            precio = self._primer_valor(
                fila, ("precio_clp", "precio", "valor", "monto", "precio_mensual", "tarifa", "costo")
            )
            minimo = maximo = precio
        if not tipo or (minimo is None and maximo is None):
            return {}
        if minimo is None:
            minimo = maximo
        if maximo is None:
            maximo = minimo
        return {"tipo": str(tipo), "min": minimo, "max": maximo}

    def obtener_benchmarks(self, rubro: str) -> dict:
        if not self.client:
            return {}
        try:
            matriz = self.client.table("matriz_plataforma").select("*").ilike("rubro", f"%{rubro}%").execute().data
            red_principal = matriz[0]["red_principal"] if matriz else "Meta"
            red_secundaria = matriz[0]["red_secundaria"] if matriz else "Google Ads"
            justificacion = matriz[0]["justificacion"] if matriz else "Estrategia estándar."
        except Exception:
            red_principal, red_secundaria, justificacion = "Meta", "Google Ads", "Estrategia estándar."

        try:
            bench = self.client.table("benchmarks_ads").select("*").ilike("industria", f"%{rubro}%").execute().data
            if bench:
                cpm = (bench[0]["cpm_min_clp"] + bench[0]["cpm_max_clp"]) / 2
                cpc = (bench[0]["cpc_min_clp"] + bench[0]["cpc_max_clp"]) / 2 if bench[0].get("cpc_min_clp") else 250
            else:
                cpm, cpc = 5000, 250
        except Exception:
            cpm, cpc = 5000, 250

        terminos_plataforma = [red_principal]
        if "meta" in red_principal.lower() and red_principal != "Meta":
            terminos_plataforma.append("Meta")
        if "google" in red_principal.lower() and red_principal != "Google":
            terminos_plataforma.append("Google")
        terminos_plataforma.append("Agencia")

        reglas_de_oro = []
        reglas_vistas = set()
        for termino in dict.fromkeys(terminos_plataforma):
            for fila in self._consultar_por_plataforma("reglas_industria", termino):
                texto = self._texto_regla(fila)
                if texto and texto not in reglas_vistas:
                    reglas_vistas.add(texto)
                    reglas_de_oro.append(texto)

        cotizaciones = []
        cotizaciones_vistas = set()
        for fila in self._consultar_por_plataforma("cotizaciones_competencia", red_principal):
            cotizacion = self._normalizar_cotizacion(fila)
            if not cotizacion:
                continue
            huella = (cotizacion["tipo"], str(cotizacion["min"]), str(cotizacion["max"]))
            if huella in cotizaciones_vistas:
                continue
            cotizaciones_vistas.add(huella)
            cotizaciones.append(cotizacion)

        print(
            f"[Ikki] Reglas de oro ({', '.join(dict.fromkeys(terminos_plataforma))}): {len(reglas_de_oro)} | "
            f"Cotizaciones competencia: {len(cotizaciones)}"
        )

        return {
            "plataforma_recomendada": red_principal,
            "plataforma_secundaria": red_secundaria,
            "justificacion": justificacion,
            "cpm_promedio_clp": int(cpm),
            "cpc_promedio_clp": int(cpc),
            "reglas_de_oro": reglas_de_oro,
            "cotizacion_competencia": cotizaciones
        }

    def obtener_contexto_relevante(self, rubro: str) -> str:
        """Mini-RAG: Busca los párrafos más relevantes en el cerebro de 347 KB."""
        brain_path = "data/contexto_maestro.txt"
        if not os.path.exists(brain_path):
            return ""

        with open(brain_path, "r", encoding="utf-8") as f:
            texto_completo = f.read()

        oraciones = texto_completo.split(". ")
        palabras_clave = [rubro.lower(), "ventas", "clientes", "anuncios", "presupuesto", "conversión", "meta ads", "google ads"]
        relevantes = []
        
        for oracion in oraciones:
            if any(palabra in oracion.lower() for palabra in palabras_clave):
                relevantes.append(oracion)

        if len(relevantes) > 50:
            relevantes = relevantes[:50]
        
        contexto = ". ".join(relevantes)
        return contexto[:5000] # Límite duro de 5000 caracteres

    def generar_copywriting(self, rubro: str, prospecto_nombre: str) -> list[dict]:
        contexto_ia = self.obtener_contexto_relevante(rubro)
        
        if contexto_ia:
            print(f"🧠 Mini-RAG activado: Encontrados {len(contexto_ia)} caracteres relevantes para '{rubro}'.")
            # Construir el Prompt Definitivo
            messages = construir_prompt(rubro, prospecto_nombre, contexto_ia)
            
            # Imprimimos el System Prompt para ver la inyección del conocimiento
            print("\n--- PREVISUALIZACIÓN DEL PROMPT PARA LA IA ---")
            print(messages[0]["content"][:500] + "...\n[CONOCIMIENTO INYECTADO]...")
            print("----------------------------------------------\n")
        else:
            log.warning("⚠️ No se encontró contexto relevante.")

        # Generación (Mock Actual hasta Diciembre)
        if USE_MOCK_LLM:
            log.info("Usando Mock de Copywriting ($0 costo)")
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
        
        proyecciones = {}
        if benchmarks.get("cpm_promedio_clp"):
            cpm = benchmarks["cpm_promedio_clp"]
            impresiones = int((presupuesto_pauta / cpm) * 1000)
            clics = int(impresiones * 0.01)
            proyecciones = {
                "impresiones_estimadas": impresiones,
                "clics_estimados": clics,
                "nota": "Cálculo basado en CPM/CPC reales (Benchmarks 2026)."
            }

        recomendacion = "APROBAR: Campaña rentable." if fee["total_facturar_clp"] >= 200000 else "RECHAZAR: Ticket muy bajo."
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
