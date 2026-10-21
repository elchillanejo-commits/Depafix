"""
simulador_kimi.py — Preview del payload que se enviará a Kimi/OpenAI en Diciembre.

No realiza llamadas reales a la API (costo $0). Solo valida:
- Cálculo de fees del motor.
- Extracción del contexto RAG.
- Construcción del payload de mensajes con prompt_engineer.
"""
from src.agencia.motor_ikki import AgenciaIkkiMotor
from src.agencia.prompt_engineer import construir_prompt


def main():
    rubro = "inmobiliaria"
    cliente = "inmobiliaria_demo"
    presupuesto_pauta = 500000

    motor = AgenciaIkkiMotor()

    print("=" * 70)
    print("SIMULADOR KIMI — AGENCIA IKKI")
    print("=" * 70)
    print(f"Rubro:       {rubro}")
    print(f"Cliente:     {cliente}")
    print(f"Presupuesto: ${presupuesto_pauta:,} CLP".replace(",", "."))

    fee = motor.calcular_fee_campana(presupuesto_pauta)
    print("\n--- FEE CALCULADO ---")
    for clave, valor in fee.items():
        print(f"{clave}: ${valor:,}".replace(",", "."))

    print("\n--- CONTEXTO RAG ---")
    contexto_rag = motor.obtener_contexto_relevante(rubro)
    print(f"Caracteres extraídos: {len(contexto_rag)}")
    print(f"Vista previa: {contexto_rag[:200]}...")

    messages = construir_prompt(rubro, cliente, contexto_rag)
    system_prompt = messages[0]["content"]
    user_prompt = messages[1]["content"]

    print("\n--- PREVIEW SYSTEM PROMPT (primeros 300 caracteres) ---")
    print(system_prompt[:300] + "...")
    print(f"\n[Longitud total del system prompt: {len(system_prompt)} caracteres]")

    print("\n--- USER PROMPT ---")
    print(user_prompt)

    print("\n--- LLAMADA REAL A KIMI (DICIEMBRE) ---")
    print("El siguiente bloque quedará activo al conectar la API real:\n")

    # from openai import OpenAI
    # client = OpenAI(api_key="TU_API_KEY", base_url="https://api.moonshot.cn/v1")
    # response = client.chat.completions.create(model="moonshot-v1-8k", messages=messages)
    # print(response.choices[0].message.content)


if __name__ == "__main__":
    main()
