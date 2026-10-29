import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
api_key = os.getenv("MOONSHOT_API_KEY")
print(f"Clave detectada: {api_key[:10]}... (longitud: {len(api_key) if api_key else 0})")

if not api_key:
    print("❌ No se encontró MOONSHOT_API_KEY en el .env")
    exit(1)

client = OpenAI(
    api_key=api_key,
    base_url="https://api.moonshot.cn/v1"
)

try:
    response = client.chat.completions.create(
        model="moonshot-v1-8k",
        messages=[{"role": "user", "content": "Hola, dime solo 'funciona'"}]
    )
    print("✅ Respuesta de Kimi:", response.choices[0].message.content)
except Exception as e:
    print(f"❌ Error: {e}")
