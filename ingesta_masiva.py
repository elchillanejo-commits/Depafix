#!/usr/bin/env python3
import os, time, sys
from core.rag_local import RAGLocal
from core.transcriber import get_transcript_text

def chunk_text(text, max_chars=2000, overlap=200):
    if len(text) <= max_chars:
        return [text]
    chunks, start = [], 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        if end < len(text):
            last_space = text.rfind(' ', start, end)
            if last_space > start + max_chars//2:
                end = last_space
        chunks.append(text[start:end].strip())
        start = end - overlap if end < len(text) else len(text)
    return chunks

def procesar(url, rag):
    try:
        print(f"📥 Procesando: {url}")
        texto = get_transcript_text(url)
        if len(texto.strip()) < 100:
            print("⚠️  Transcripción corta o no disponible")
            return
        frags = chunk_text(texto)
        for i, f in enumerate(frags):
            rag.store(
                titulo=f"Video {url[-11:]} (fragmento {i+1}/{len(frags)})",
                contenido=f,
                metadata={"fuente": url, "fragmento": i+1, "total": len(frags)}
            )
        print(f"✅ {len(frags)} fragmentos guardados")
    except Exception as e:
        print(f"❌ Error: {e}")

def main():
    if not os.getenv('VIRTUAL_ENV'):
        print("⚠️  Activa el entorno: source .venv/bin/activate")
        sys.exit(1)
    if os.path.exists('urls.txt'):
        with open('urls.txt', 'r') as f:
            urls = [line.strip() for line in f if line.strip() and not line.startswith('#')]
    else:
        print("⚠️  No existe urls.txt. Usando lista de ejemplo...")
        urls = []
    if not urls:
        print("❌ No hay URLs para procesar. Crea urls.txt con una URL por línea.")
        return
    rag = RAGLocal()
    print(f"📋 Se procesarán {len(urls)} videos.")
    for url in urls:
        procesar(url, rag)
        time.sleep(1.5)
    print(f"✅ Total de fragmentos en la base: {rag.index.ntotal}")

if __name__ == "__main__":
    main()
