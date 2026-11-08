import os
from dotenv import load_dotenv
from supabase import create_client
from sentence_transformers import SentenceTransformer

load_dotenv()
s = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_SERVICE_ROLE_KEY'))
model = SentenceTransformer('intfloat/multilingual-e5-small')

tests = [
    ("Agua", "match_coach_agua", "¿Cómo configuro los envíos de Shopify a Chile?"),
    ("Aire", "match_coach_aire", "¿Cómo creo una campaña de Meta Ads para vender más?"),
    ("Fuego", "match_coach_fuego", "¿Cómo automatizo un script en Python para leer PDFs?")
]

for nombre, rpc, pregunta in tests:
    print(f"\n{'='*60}")
    print(f"🤖 PROBANDO COACH {nombre.upper()}")
    print(f"❓ Pregunta: {pregunta}")
    print(f"{'='*60}")
    try:
        vector = model.encode(f"query: {pregunta}").tolist()
        res = s.rpc(rpc, {"query_embedding": vector, "match_count": 3}).execute()
        if not res.data:
            print(f"❌ FALLO: La tabla {nombre} está vacía.")
            continue
        for i, r in enumerate(res.data, 1):
            print(f"[{i}] sim={r['similarity']:.4f}")
            print(f"    {r['contenido'][:250]}...")
    except Exception as e:
        print(f"❌ ERROR: {e}")

print("\n" + "="*60)
print("✅ PRUEBAS COMPLETADAS")
