import os
import sys
import json

# --- Fix: src/ vive en el proyecto DepaFix, no en DepaFix_Maestro ---
RUTA_PROYECTO_DEPAFIX = "/home/ibar/PROYECTOS/Proyectos/DepaFix"
if RUTA_PROYECTO_DEPAFIX not in sys.path:
    sys.path.insert(0, RUTA_PROYECTO_DEPAFIX)

from dotenv import load_dotenv

load_dotenv()
if not os.environ.get("SUPABASE_URL"):
    os.environ["SUPABASE_URL"] = os.popen("grep SUPABASE_URL ~/.depafix_secrets | cut -d'=' -f2").read().strip()
    os.environ["SUPABASE_SERVICE_ROLE_KEY"] = os.popen("grep SUPABASE_SERVICE_ROLE_KEY ~/.depafix_secrets | cut -d'=' -f2").read().strip()

from supabase import create_client
from sentence_transformers import SentenceTransformer
from src.trading.rag_helper import consultar_conocimiento  # import corregido via sys.path

PREGUNTA = "¿Cuál es la cláusula de exención de responsabilidad en el contrato de auditoría?"

print("Buscando en la base de datos local...")

print("\n=== 1. RAG genérico (src.trading.rag_helper) ===")
try:
    print(consultar_conocimiento(PREGUNTA, limite=2))
except Exception as e:
    print(f"Error rag_helper: {e}")

print("\n=== 2. Búsqueda directa en metal_knowledge (fuente contrato de auditoría) ===")
sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])

modelo = SentenceTransformer("intfloat/multilingual-e5-small")
vector = modelo.encode(f"query: {PREGUNTA}").tolist()

# 1) RPC vectorial sobre metal_knowledge
mejor = []
try:
    resp = sb.rpc("match_metal_knowledge", {
        "query_embedding": vector,
        "match_threshold": 0.0,
        "match_count": 5,
    }).execute()
    mejor = resp.data or []
except Exception as e:
    print(f"  ⚠️ RPC match_metal_knowledge falló: {e}")

# 2) Filtro por contenido (ilike) para no depender solo del ranking semántico
filtradas = []
for patron in ["%exención de responsabilidad%", "%exencion de responsabilidad%", "%exención%"]:
    try:
        r = sb.table("metal_knowledge").select("id,contenido,metadata,embedding").ilike("contenido", patron).limit(500).execute()
        if r.data:
            filtradas = r.data
            break
    except Exception as e:
        print(f"  ⚠️ ilike '{patron}' falló: {e}")

# Re-rank local: todos los candidatos, coseno contra la pregunta
import numpy as np

def sim(emb):
    try:
        if isinstance(emb, str):
            emb = json.loads(emb)
        a = np.asarray(vector, dtype=float)
        b = np.asarray(emb, dtype=float)
        den = np.linalg.norm(a) * np.linalg.norm(b)
        return float(np.dot(a, b) / den) if den > 0 else 0.0
    except Exception:
        return 0.0

candidatos = {row["id"]: row for row in mejor}
for row in filtradas:
    candidatos.setdefault(row["id"], row)

ranking = sorted(candidatos.values(), key=lambda x: sim(x.get("embedding")), reverse=True)

if not ranking:
    print("No se encontró conocimiento en metal_knowledge.")
else:
    for i, row in enumerate(ranking[:3], 1):
        meta = row.get("metadata") or {}
        print(f"\n[{i}] fuente={meta.get('fuente')} | id={row['id']} | sim={sim(row.get('embedding')):.4f}")
        print("-" * 70)
        print((row.get("contenido") or "")[:3000])

    # Imprimir la cláusula completa desde la fuente del mejor resultado
    mejor_fuente = (ranking[0].get("metadata") or {}).get("fuente")
    if mejor_fuente:
        try:
            filas_fuente = sb.table("metal_knowledge").select("id,contenido").filter("metadata->>fuente", "eq", mejor_fuente).order("id").execute()
            filas_fuente = sorted(filas_fuente.data or [], key=lambda x: x["id"])
            texto_completo = "\n".join(f["contenido"] for f in filas_fuente)
            lineas = texto_completo.split("\n")
            inicio = next((i for i, l in enumerate(lineas) if "EXENCIÓN DE RESPONSABILIDAD" in l.upper()), None)
            if inicio is not None:
                fin = next((i for i in range(inicio + 1, len(lineas)) if lineas[i].lstrip().startswith("## ")), len(lineas))
                print("\n" + "=" * 70)
                print(f"CLÁUSULA COMPLETA (fuente: {mejor_fuente})")
                print("=" * 70)
                print("\n".join(lineas[max(0, inicio - 1):fin]))
        except Exception as e:
            print(f"  ⚠️ No se pudo extraer la cláusula completa: {e}")
