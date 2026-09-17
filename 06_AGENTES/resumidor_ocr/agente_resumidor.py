#!/usr/bin/env python3
"""
Agente Resumidor Híbrido (OCR local + Resumen vía Claude API).
Uso:
  python3 agente_resumidor.py --archivo documento.pdf
  python3 agente_resumidor.py --imagen captura.png
  python3 agente_resumidor.py --texto "Texto largo a resumir..."
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Ajustar ruta del proyecto para importar core
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from core.db_manager import DatabaseManager
from core.resiliencia import red_segura, RedFailSafeError

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

TESSERACT_BIN = "/usr/bin/tesseract"
CLAUDE_MODEL = "claude-sonnet-5"
MAX_TOKENS_RESUMEN = 500


def extraer_texto_imagen(path_imagen: str) -> str:
    try:
        from PIL import Image
        import pytesseract
        pytesseract.pytesseract.tesseract_cmd = TESSERACT_BIN
        img = Image.open(path_imagen)
        texto = pytesseract.image_to_string(img, lang="spa")
        return texto.strip()
    except ImportError:
        raise RuntimeError("Instalá pytesseract y Pillow: pip install pytesseract Pillow")
    except Exception as e:
        raise RuntimeError(f"Error al procesar la imagen: {e}")


def extraer_texto_pdf(path_pdf: str) -> str:
    import subprocess
    try:
        result = subprocess.run(
            ["pdftotext", "-layout", path_pdf, "-"],
            capture_output=True, text=True, check=True
        )
        texto = result.stdout.strip()
        if len(texto) > 50:
            return texto
    except Exception:
        pass
    try:
        from pdf2image import convert_from_path
        import pytesseract
        pytesseract.pytesseract.tesseract_cmd = TESSERACT_BIN
        paginas = convert_from_path(path_pdf)
        texto = "\n".join(pytesseract.image_to_string(p, lang="spa") for p in paginas)
        return texto.strip()
    except ImportError:
        raise RuntimeError("Instalá pdf2image y pytesseract: pip install pdf2image pytesseract")
    except Exception as e:
        raise RuntimeError(f"Error al procesar el PDF: {e}")


@red_segura(max_reintentos=2, latencia_max=30.0, operacion="resumir con Claude")
def resumir_con_claude(texto: str, max_tokens: int = MAX_TOKENS_RESUMEN) -> str:
    import anthropic
    api_key = os.getenv("CLAUDE_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("CLAUDE_API_KEY no definida en .env")
    cliente = anthropic.Anthropic(api_key=api_key)
    respuesta = cliente.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=max_tokens,
        messages=[{
            "role": "user",
            "content": f"Resumí el siguiente texto en español, destacando los puntos clave y manteniendo un tono profesional:\n\n{texto}"
        }]
    )
    return respuesta.content[0].text


def generar_resumen_mock(texto: str, max_chars: int = 300) -> str:
    """Resumen de respaldo cuando la API de Claude no está disponible (sin
    clave configurada o falla de red), para poder validar el resto del
    flujo (OCR/extracción + persistencia) sin depender de la API."""
    extracto = " ".join(texto.split())
    if len(extracto) > max_chars:
        extracto = extracto[:max_chars].rsplit(" ", 1)[0] + "..."
    return f"[RESUMEN MOCK — Claude API no disponible]\n{extracto}"


def guardar_resumen(texto_original: str, resumen: str, modelo: str, metadata: Optional[dict] = None) -> int:
    db = DatabaseManager().get_service_client()
    payload = {
        "texto_original": texto_original[:5000],
        "resumen": resumen,
        "modelo_usado": modelo,
        "metadata": json.dumps(metadata or {}, ensure_ascii=False),
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    resp = db.table("resumenes").insert(payload).execute()
    if resp.data:
        return resp.data[0]["id"]
    raise RuntimeError("No se pudo insertar el resumen en Supabase")


def resumir_y_guardar(texto: str, max_tokens: int = MAX_TOKENS_RESUMEN, fuente: str = "texto_directo") -> dict:
    """Resume `texto` (con fallback a mock si Claude no está disponible o
    falla) y persiste el resultado en Supabase. Punto de entrada compartido
    por la CLI y por el endpoint /api/agentes/resumir de api.py."""
    if not texto or len(texto) < 10:
        raise ValueError("No se pudo extraer texto suficiente.")

    logger.info("Texto a resumir: %d caracteres.", len(texto))

    api_key = os.getenv("CLAUDE_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        logger.warning("CLAUDE_API_KEY no definida — usando resumen mockeado.")
        resumen = generar_resumen_mock(texto)
        modelo_usado = "mock-sin-api-key"
    else:
        try:
            resumen = resumir_con_claude(texto, max_tokens=max_tokens)
            modelo_usado = CLAUDE_MODEL
        except RedFailSafeError as e:
            logger.warning("Falló la llamada a Claude (%s) — usando resumen mockeado.", e)
            resumen = generar_resumen_mock(texto)
            modelo_usado = "mock-fallback"
    logger.info("Resumen generado: %d caracteres.", len(resumen))

    metadata = {
        "fuente": fuente,
        "caracteres_original": len(texto),
        "caracteres_resumen": len(resumen),
    }
    resumen_id = None
    try:
        resumen_id = guardar_resumen(texto, resumen, modelo_usado, metadata)
        logger.info("✅ Resumen guardado en Supabase con ID=%d", resumen_id)
    except Exception as e:
        logger.warning("No se pudo guardar en Supabase (%s) — se devuelve igual el resumen.", e)

    return {"id": resumen_id, "resumen": resumen, "modelo_usado": modelo_usado}


def main():
    parser = argparse.ArgumentParser(description="Agente Resumidor Híbrido")
    grupo = parser.add_mutually_exclusive_group(required=True)
    grupo.add_argument("--archivo", help="Ruta a un archivo PDF")
    grupo.add_argument("--imagen", help="Ruta a una imagen (PNG, JPG)")
    grupo.add_argument("--texto", help="Texto directo a resumir")
    parser.add_argument("--max-tokens", type=int, default=MAX_TOKENS_RESUMEN, help="Tokens máximos para el resumen")
    args = parser.parse_args()

    try:
        if args.archivo:
            logger.info("Procesando archivo: %s", args.archivo)
            ext = Path(args.archivo).suffix.lower()
            texto = extraer_texto_pdf(args.archivo) if ext == ".pdf" else extraer_texto_imagen(args.archivo)
        elif args.imagen:
            logger.info("Procesando imagen: %s", args.imagen)
            texto = extraer_texto_imagen(args.imagen)
        else:
            texto = args.texto

        resultado = resumir_y_guardar(
            texto,
            max_tokens=args.max_tokens,
            fuente=args.archivo or args.imagen or "texto_directo",
        )

        print("\n" + "=" * 60)
        print("RESUMEN:")
        print("=" * 60)
        print(resultado["resumen"])
        print("=" * 60)

    except ValueError as e:
        logger.error("%s", e)
        sys.exit(1)
    except Exception as e:
        logger.error("Error: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
