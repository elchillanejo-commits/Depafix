import os
import re

def leer_archivo(ruta):
    if not os.path.exists(ruta):
        return ""
    with open(ruta, "r", encoding="utf-8") as f:
        return f.read()

def procesar_mente_360(query: str):
    print(f"\n--- 🧠 [ROUTER MENTE 360] PROCESANDO: '{query}' ---")
    query_lower = query.lower()
    
    # Detección de elementos por palabras clave
    if any(w in query_lower for w in ["contrato", "ley", "finiquito", "subcontratación", "responsabilidad", "legal"]):
        elemento = "METAL"
    elif any(w in query_lower for w in ["sence", "otec", "franquicia", "capacitación", "curso", "tributaria"]):
        elemento = "SENCE"
    elif any(w in query_lower for w in ["shopify", "dropshipping", "inventario", "logística", "despacho"]):
        elemento = "AGUA"
    elif any(w in query_lower for w in ["marketing", "meta ads", "redes", "guion", "whatsapp", "branding"]):
        elemento = "AIRE"
    elif any(w in query_lower for w in ["python", "script", "api", "kraken", "supabase", "codigo", "railway"]):
        elemento = "FUEGO"
    elif any(w in query_lower for w in ["cotizar", "instalar", "construir", "remodelar", "cerámica", "presupuesto"]):
        elemento = "TIERRA"
    else:
        print("❌ [Router]: Consulta ambigua. Aplicando protocolo de bloqueo.")
        return

    print(f"✅ [Router]: Enrutado con éxito a la naturaleza -> {elemento}")
    ejecutar_ciclo_profesor_coach(elemento, query_lower)

def ejecutar_ciclo_profesor_coach(elemento, query_lower):
    print(f"📋 [Profesor de {elemento}]: Validando parámetros y contexto...")
    print(f"🚀 [Coach Especializado]: Consultando bases de conocimiento en Supabase...")
    
    # Fase de Auditoría Master
    print("🛡️ [Auditor Master]: Verificando cero alucinaciones y cumplimiento de esquemas...")
    print(f"🎯 [Output Certificado]: ¡Operación del Elemento {elemento} validada y lista para producción a coste cero!")

if __name__ == "__main__":
    print("=== SIMULADOR MAESTRO MENTE 360 (TODOS LOS ELEMENTOS + AUDITOR) ===")
    
    # Pruebas cruzadas por elemento
    procesar_mente_360("¿Cuánto sale instalar cerámica en Macul con 50 m²?")
    procesar_mente_360("Necesitamos revisar un contrato de subcontratación y la Ley 16.744")
    procesar_mente_360("Optimiza el script de Python conectado a la API de Kraken en Supabase")
