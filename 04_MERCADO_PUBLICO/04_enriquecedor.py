#!/usr/bin/env python3
import argparse
import sys
import re
from collections import Counter
from typing import List
sys.path.insert(0, '/home/ibar/Proyectos/DepaFix')
from core.db_manager import DatabaseManager

try:
    import yake
    USE_YAKE = True
except ImportError:
    USE_YAKE = False
    print("ℹ️ YAKE no instalado. Usando método simple.", file=sys.stderr)

STOPWORDS = set([
    "de", "la", "que", "el", "en", "y", "a", "los", "del", "las", "un", "por", "con", "no", "su", "para", "es", "al", "lo",
    "como", "más", "pero", "sus", "le", "ya", "este", "entre", "desde", "todo", "nos", "durante", "según", "cada", "uno",
    "otro", "todos", "tiene", "fue", "han", "sido", "ser", "era", "son", "está", "están", "estar", "tenía", "hasta", "solo",
    "como", "cuando", "muy", "sin", "sobre", "también", "hace", "puede", "debe", "contra"
])

def extraer_palabras_clave_simple(texto: str, top_n: int = 10) -> List[str]:
    texto_limpio = re.sub(r'[^\w\s]', ' ', texto.lower())
    palabras = texto_limpio.split()
    filtradas = [p for p in palabras if p not in STOPWORDS and len(p) > 3]
    return [p for p, _ in Counter(filtradas).most_common(top_n)]

def enriquecer_lotes(limit: int = 100, dry_run: bool = False) -> int:
    db = DatabaseManager().get_service_client()
    tabla = "licitaciones"
    
    result = db.table(tabla).select("id, codigo_licitacion, titulo, descripcion").is_("palabras_clave", "[]").limit(limit).execute()
    registros = result.data
    if not registros:
        print("✅ No hay licitaciones para enriquecer.")
        return 0
    
    print(f"🔍 Procesando {len(registros)} licitaciones...")
    actualizados = 0
    
    for reg in registros:
        texto = f"{reg.get('titulo', '')} {reg.get('descripcion', '')}"
        if not texto.strip():
            continue
        
        if USE_YAKE:
            extractor = yake.KeywordExtractor(lan="es", top=10, stopwords=STOPWORDS)
            keywords = [kw[0] for kw in extractor.extract_keywords(texto)]
        else:
            keywords = extraer_palabras_clave_simple(texto)
        
        if dry_run:
            print(f"[DRY RUN] {reg['codigo_licitacion']}: {keywords}")
        else:
            try:
                db.table(tabla).update({"palabras_clave": keywords}).eq("id", reg["id"]).execute()
                actualizados += 1
            except Exception as e:
                print(f"❌ Error actualizando {reg['codigo_licitacion']}: {e}", file=sys.stderr)
    
    print(f"✅ {actualizados} licitaciones enriquecidas.")
    return actualizados

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    enriquecer_lotes(limit=args.limit, dry_run=args.dry_run)

if __name__ == "__main__":
    main()
