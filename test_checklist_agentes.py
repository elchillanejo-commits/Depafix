import os
from dotenv import load_dotenv
from supabase import create_client
from sentence_transformers import SentenceTransformer

load_dotenv()
s = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_SERVICE_ROLE_KEY'))
model = SentenceTransformer('intfloat/multilingual-e5-small')

# Checklist del Supervisor (Nemotron)
tests = [
    {
        "coach": "Agua",
        "rpc": "match_coach_agua",
        "pregunta": "¿Cómo configuro un sistema de dropshipping con Shopify y pago contra entrega?",
        "terminos_clave": ["dropshipping", "shopify", "contra entrega", "logística"]
    },
    {
        "coach": "Aire",
        "rpc": "match_coach_aire",
        "pregunta": "¿Cómo optimizo una campaña de Meta Ads para mejorar el ROAS?",
        "terminos_clave": ["roas", "cpa", "meta ads", "campaña", "optimización"]
    },
    {
        "coach": "Fuego",
        "rpc": "match_coach_fuego",
        "pregunta": "¿Cómo puedo hacer un pentesting básico y configurar un firewall?",
        "terminos_clave": ["pentesting", "firewall", "ciberseguridad", "protección"]
    }
]

for test in tests:
    print(f"\n{'='*60}")
    print(f"🤖 PROBANDO COACH {test['coach'].upper()}")
    print(f"❓ Pregunta: {test['pregunta']}")
    print(f"{'='*60}")
    try:
        vector = model.encode(f"query: {test['pregunta']}").tolist()
        res = s.rpc(test["rpc"], {"query_embedding": vector, "match_count": 3}).execute()
        
        if not res.data:
            print(f"❌ FALLO: La tabla {test['coach']} está vacía.")
            continue
            
        for i, r in enumerate(res.data, 1):
            contenido = r['contenido'].lower()
            sim = r['similarity']
            
            # Validación de términos clave
            encontrados = [t for t in test['terminos_clave'] if t in contenido]
            pasa_terminos = len(encontrados) >= 2
            pasa_similitud = sim > 0.80
            
            estado = "✅ PASS" if (pasa_similitud and pasa_terminos) else "⚠️ FAIL"
            
            print(f"\n[{i}] sim={sim:.4f} | {estado}")
            print(f"    Términos encontrados: {encontrados}")
            print(f"    Contenido: {contenido[:250]}...")
            
    except Exception as e:
        print(f"❌ ERROR: {e}")

print("\n" + "="*60)
print("✅ PRUEBAS COMPLETADAS")
