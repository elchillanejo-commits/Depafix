from core.rag_local import RAGLocal
from core.transcriber import get_transcript_text

url = "https://www.youtube.com/watch?v=YOUR_VIDEO_ID"  # Cámbialo
texto = get_transcript_text(url)
print(f"Transcripción: {len(texto)} caracteres")

rag = RAGLocal()
rag.store(fuente=url, titulo="Video de prueba", contenido=texto[:4000])
print("✅ Guardado localmente")

resultados = rag.search("responsabilidad civil extracontractual")
for r in resultados:
    print(f"- {r['titulo']} (sim: {r['similarity']:.2f})")
