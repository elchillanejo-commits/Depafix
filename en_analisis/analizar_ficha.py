import os
import sys
import json
import urllib.request

# Configuración de la API (usamos el modelo que ya te funcionó)
API_KEY = os.environ.get('OPENROUTER_API_KEY')
URL_API = "https://openrouter.ai/api/v1/chat/completions"
MODELO = "google/gemma-3-27b-it:free"

def analizar_con_ia(texto_ficha):
    prompt_sistema = """Eres un experto en Eneagrama y ventas (B2B). 
Analiza la ficha del prospecto y devuelve SOLO un JSON con la siguiente estructura:
{
  "eneatipo": "5w6",
  "arquetipo": "Descartes",
  "diagnostico": "Resumen psicológico de 2 líneas.",
  "estrategia": "Estrategia de acercamiento de 1 línea.",
  "speech": "Mensaje de WhatsApp personalizado para contactarlo."
}
"""
    
    payload = {
        "model": MODELO,
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": prompt_sistema},
            {"role": "user", "content": texto_ficha}
        ]
    }
    
    req = urllib.request.Request(
        URL_API,
        data=json.dumps(payload).encode(),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {API_KEY}"
        }
    )
    
    try:
        respuesta = urllib.request.urlopen(req, timeout=60)
        datos = json.loads(respuesta.read())
        contenido = datos['choices'][0]['message']['content']
        return json.loads(contenido)
    except Exception as e:
        print(f"Error llamando a la IA: {e}")
        return None

if len(sys.argv) < 2:
    print("Uso: python3 en_analisis/analizar_ficha.py <nombre_archivo_sin_extension>")
    sys.exit(1)

nombre_base = sys.argv[1]
ruta_md = f"en_analisis/{nombre_base}.md"

if not os.path.exists(ruta_md):
    print(f"Error: No se encuentra el archivo {ruta_md}")
    sys.exit(1)

with open(ruta_md, "r", encoding="utf-8") as f:
    texto_ficha = f.read()

print(f"🧠 Analizando ficha de {nombre_base} con IA...")
resultado = analizar_con_ia(texto_ficha)

if resultado:
    # Añadimos el resultado al final del archivo Markdown
    with open(ruta_md, "a", encoding="utf-8") as f:
        f.write("\n\n=== ANÁLISIS IA ===\n")
        f.write(f"ENEATIPO: {resultado.get('eneatipo')}\n")
        f.write(f"ARQUETIPO: {resultado.get('arquetipo')}\n")
        f.write(f"DIAGNOSTICO: {resultado.get('diagnostico')}\n")
        f.write(f"ESTRATEGIA: {resultado.get('estrategia')}\n")
        f.write(f"SPEECH: {resultado.get('speech')}\n")
    
    print("\n✅ Análisis completado y guardado en el archivo .md")
    print("-" * 50)
    print(f"ENEATIPO: {resultado.get('eneatipo')} / {resultado.get('arquetipo')}")
    print(f"DIAGNOSTICO: {resultado.get('diagnostico')}")
    print(f"SPEECH: {resultado.get('speech')}")
    print("-" * 50)
else:
    print("❌ No se pudo generar el análisis.")
