import os
import pandas as pd
import time
from openai import OpenAI
from dotenv import load_dotenv

# 1. Cargar variables de entorno
load_dotenv()
API_KEY = os.getenv("MOONSHOT_API_KEY")

if not API_KEY or API_KEY == "TU_API_KEY_DE_KIMI":
    print("❌ ERROR: No se encontró la MOONSHOT_API_KEY real en el archivo .env")
    exit(1)

# 2. Configurar el cliente de Kimi (Compatible con OpenAI)
client = OpenAI(
    api_key=API_KEY,
    base_url="https://api.moonshot.cn/v1"
)

# 3. Rutas de los archivos
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_FILE = os.path.join(BASE_DIR, "prospectos.csv")
OUTPUT_FILE = os.path.join(BASE_DIR, "resultados_finales_ia.csv")

def analizar_prospecto(row):
    """Envía los datos del prospecto a Kimi y obtiene el análisis."""
    
    nombre = str(row.get('Nombre', 'Desconocido'))
    rubro = str(row.get('Rubro', 'Desconocido'))
    rasgos = str(row.get('Personalidad', 'No especificados'))
    
    prompt = f"""
    Actúa como experto en Eneagrama y ventas.
    Estoy vendiendo departamentos en Carmen Mena 1050 a mi red de contactos del Club Stade Français (tenis/pádel).
    Mantén un ROL DE PAR, cero venta directa, cero presión.

    PERFIL A ANALIZAR:
    - Nombre: {nombre}
    - Rubro: {rubro}
    - Rasgos/Observaciones: {rasgos}

    DEVUÉLVEME EXACTAMENTE 6 VALORES SEPARADOS POR EL SÍMBOLO "|" (PIPE). SIN TEXTO EXTRA.
    1. Eneatipo (1-9, ej: 5w6)
    2. Arquetipo (ej: Descartes)
    3. Porque (Diagnóstico breve)
    4. NO_decir (Qué evitar)
    5. SI_decir (Cómo entrarle)
    6. Speech (Mensaje de WhatsApp de 3 líneas, rol de par, usando el tenis como excusa)
    """

    try:
        response = client.chat.completions.create(
            model="moonshot-v1-8k",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )
        resultado = response.choices[0].message.content.strip()
        return resultado
    except Exception as e:
        print(f"⚠️ Error analizando a {nombre}: {e}")
        return "ERROR|ERROR|ERROR|ERROR|ERROR|ERROR"

def main():
    print("🚀 Iniciando análisis de prospectos con Kimi (Moonshot)...")
    
    if not os.path.exists(INPUT_FILE):
        print(f"❌ No se encontró el archivo {INPUT_FILE}")
        return

    # Leer datos
    df = pd.read_csv(INPUT_FILE)
    resultados = []

    print(f"📊 Se encontraron {len(df)} prospectos para analizar.")

    for index, row in df.iterrows():
        nombre = row.get('Nombre', f'Fila_{index}')
        print(f"[{index+1}/{len(df)}] Analizando a: {nombre}...")
        
        analisis = analizar_prospecto(row)
        
        # Guardar la fila original + el análisis
        fila_resultado = row.to_dict()
        fila_resultado['Analisis_IA'] = analisis
        resultados.append(fila_resultado)

        # Pausa de 2 segundos para no saturar la API
        time.sleep(2)

    # Guardar resultados
    df_resultados = pd.DataFrame(resultados)
    df_resultados.to_csv(OUTPUT_FILE, index=False)
    print(f"\n✅ ¡Análisis completado! Resultados guardados en: {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
