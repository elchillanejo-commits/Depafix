#!/usr/bin/env python3
"""
descargar_youtube.py — descarga transcripciones de YouTube a .txt
Cerebro "Agua" · DepaFix Mente 360
"""
import os
import re
from youtube_transcript_api import YouTubeTranscriptApi

URLS = [
    "https://youtu.be/cWzw8xa-bYc",
    "https://youtu.be/X1tXWAOVzWM",
    "https://youtu.be/9A5m4OiF6jE",
    "https://youtu.be/sG7CYjkHQB4",
    "https://youtu.be/GdAQcaO4kSs",
    "https://youtu.be/uN3kZpbU_kU",
    "https://youtu.be/JUFaND2oyqo",
    "https://youtu.be/WBqn3TubmbE",
    "https://www.youtube.com/live/Ut6No2nfxy4",
    "https://youtu.be/SXaY1Bz8Ndk",
    "https://youtu.be/WUMBfrIAe0o",
    "https://youtu.be/v0boOqR6sI8",
    "https://youtu.be/WFAlD96Iolo",
    "https://youtu.be/JbE9mrwBDeg",
    "https://youtu.be/Xa-sTieK8Ec",
]

CARPETA_DESTINO = "/home/ibar/Documentos/Conocimiento/Agua_Dropshipping"
IDIOMAS = ['es']


def obtener_id_video(url):
    match = re.search(r'(?:v=|\/)([0-9A-Za-z_-]{11})', url)
    return match.group(1) if match else None


def extraer_texto(video_id):
    """Soporta youtube-transcript-api v1.x (fetch) y v0.x (get_transcript)."""
    try:
        api = YouTubeTranscriptApi()
        fetched = api.fetch(video_id, languages=IDIOMAS)
        return " ".join(seg.text for seg in fetched)
    except AttributeError:
        segments = YouTubeTranscriptApi.get_transcript(video_id, languages=IDIOMAS)
        return " ".join(seg['text'] for seg in segments)


def main():
    os.makedirs(CARPETA_DESTINO, exist_ok=True)
    total = len(URLS)
    ok, fail = 0, 0
    print(f"🚀 Iniciando descarga de {total} videos...")
    print(f"📁 Destino: {CARPETA_DESTINO}\n")

    for i, url in enumerate(URLS, 1):
        vid = obtener_id_video(url)
        if not vid:
            print(f"[{i}/{total}] ⚠️  URL inválida: {url}")
            fail += 1
            continue

        destino = os.path.join(CARPETA_DESTINO, f"{vid}.txt")
        if os.path.exists(destino):
            print(f"[{i}/{total}] ⏭️  Ya existe: {vid}.txt")
            ok += 1
            continue

        try:
            texto = extraer_texto(vid)
        except Exception as e:
            print(f"[{i}/{total}] ⚠️  Saltado {url}: {e}")
            fail += 1
            continue

        with open(destino, "w", encoding="utf-8") as f:
            f.write(texto)
        print(f"[{i}/{total}] ✅ {vid}.txt ({len(texto)} chars)")
        ok += 1

    print(f"\n🎉 Proceso terminado. OK={ok}  Fallidos={fail}")
    print(f"   Revisa: {CARPETA_DESTINO}")


if __name__ == "__main__":
    main()
