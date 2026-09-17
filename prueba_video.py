from core.rag_local import RAGLocal
from core.transcriber import get_transcript_text
url = "https://www.youtube.com/watch?v=ID_REAL"  # Cámbialo
texto = get_transcript_text(url)
rag = RAGLocal()
rag.store(url, "Video prueba", texto[:4000])
print("✅ Guardado")
for r in rag.search("responsabilidad civil", 3):
    print(f"- {r['titulo']} ({r['similarity']:.2f})")
