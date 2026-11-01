#!/usr/bin/env python3
import sys
from pathlib import Path
import yt_dlp

DESTINO = Path("/home/ibar/Documentos/Conocimiento/Agua_Dropshipping/")
DESTINO.mkdir(parents=True, exist_ok=True)

def descargar_subtitulos(url):
    print(f"\nProcesando: {url}")
    
    ydl_opts = {
        'skip_download': True,
        'writesubtitles': True,
        'writeautomaticsub': True,
        'subtitleslangs': ['es', 'es-orig'],
        'subtitlesformat': 'vtt',
        'outtmpl': str(DESTINO / '%(title)s.%(ext)s'),
        'quiet': True,
        'no_warnings': True,
        'cookiefile': '/home/ibar/DepaFix_Maestro/cookies.txt',
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            archivo_base = ydl.prepare_filename(info).rsplit('.', 1)[0]
            
            vtt_files = list(DESTINO.glob(f"{Path(archivo_base).name}*.vtt"))
            
            if not vtt_files:
                print(f"  [WARN] No se encontraron subtítulos para: {info.get('title')}")
                return False
                
            vtt_path = vtt_files[0]
            txt_path = DESTINO / f"{vtt_path.name.replace('.vtt', '.txt')}"
            
            with open(vtt_path, 'r', encoding='utf-8') as f_in, open(txt_path, 'w', encoding='utf-8') as f_out:
                for line in f_in:
                    if '-->' in line or line.startswith('WEBVTT') or not line.strip():
                        continue
                    linea_limpia = line.strip().replace('<c>', '').replace('</c>', '')
                    f_out.write(linea_limpia + "\n")
            
            vtt_path.unlink()
            print(f"  [OK] Guardado: {txt_path.name}")
            return True
            
    except Exception as e:
        print(f"  [ERROR] Falló: {url} | {str(e)[:100]}")
        return False

def main():
    if len(sys.argv) < 2:
        print("Uso: python3 extractor_youtube.py URL1 URL2 URL3 ...")
        sys.exit(1)
        
    urls = sys.argv[1:]
    print(f"Se procesarán {len(urls)} videos.")
    
    exitos = 0
    for url in urls:
        if descargar_subtitulos(url):
            exitos += 1
            
    print(f"\nResumen: {exitos}/{len(urls)} transcripciones guardadas en {DESTINO}")

if __name__ == "__main__":
    main()
