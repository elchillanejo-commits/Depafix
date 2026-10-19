"""
procesar_conocimiento.py — Días 9 y 10 (Gantt Ikki).
Toma los textos crudos de Supabase, extrae insights (Mock) y arma el System Prompt.
"""
import os
import json
import logging
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()
log = logging.getLogger(__name__)

USE_MOCK_LLM = os.environ.get("IKKI_USE_MOCK", "1") == "1"

class ProcesadorIkki:
    def __init__(self):
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        self.client = create_client(url, key)

    def extraer_insights(self, texto: str) -> dict:
        """Día 9: Extrae resumen y palabras clave (Mock para $0)."""
        if USE_MOCK_LLM:
            log.info("Mockeando extracción de insights ($0 costo)")
            # Simulamos lo que haría la IA
            return {
                "resumen": "El experto habla sobre estrategias de marketing inmobiliario y cómo captar leads usando video.",
                "palabras_clave": ["marketing", "inmobiliario", "leads", "video"]
            }
        
        # Aquí iría la llamada real a Kimi/Anthropic
        return {"resumen": "Pendiente API real", "palabras_clave": []}

    def procesar_pendientes(self) -> int:
        """Busca filas sin resumen, las procesa y actualiza en Supabase."""
        # 1. Buscar filas donde 'resumen' es NULL
        pendientes = self.client.table("knowledge_entries").select("id, contenido, titulo").is_("resumen", "null").execute().data
        
        if not pendientes:
            log.info("No hay conocimiento pendiente de procesar.")
            return 0

        log.info(f"Procesando {len(pendientes)} entradas...")
        for row in pendientes:
            insights = self.extraer_insights(row['contenido'])
            
            # 2. Actualizar en Supabase (Día 9)
            self.client.table("knowledge_entries").update({
                "resumen": insights["resumen"],
                "palabras_clave": insights["palabras_clave"]
            }).eq("id", row["id"]).execute()
            
            log.info(f"✅ Entrada ID {row['id']} procesada.")
        
        return len(pendientes)

    def generar_system_prompt(self) -> str:
        """Día 10: Construye el System Prompt con el conocimiento inyectado."""
        log.info("Generando System Prompt para Ikki (Día 10)...")
        
        # Traemos los 5 resúmenes más recientes
        conocidos = self.client.table("knowledge_entries").select("titulo, resumen").not_.is_("resumen", "null").limit(5).execute().data
        
        prompt = "Eres Ikki, un experto estratega de marketing digital.\n"
        prompt += "Tu conocimiento se basa en las siguientes fuentes:\n\n"
        
        for c in conocidos:
            prompt += f"- {c['titulo']}: {c['resumen']}\n"
            
        prompt += "\nRedacta copys persuasivos usando estas enseñanzas."
        
        # Guardar en un archivo local para que motor_ikki lo lea
        os.makedirs("src/agencia/prompts", exist_ok=True)
        with open("src/agencia/prompts/ikki_system.txt", "w") as f:
            f.write(prompt)
            
        log.info("✅ Archivo guardado en src/agencia/prompts/ikki_system.txt")
        return prompt

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    procesador = ProcesadorIkki()
    
    # Ejecutamos Día 9
    n = procesador.procesar_pendientes()
    
    # Ejecutamos Día 10
    if n > 0:
        prompt_final = procesador.generar_system_prompt()
        print("\n--- SYSTEM PROMPT GENERADO ---")
        print(prompt_final)
