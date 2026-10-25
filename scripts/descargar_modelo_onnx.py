"""
descargar_modelo_onnx.py — Baja intfloat/multilingual-e5-small (ONNX) para el RAG.

Revisión fijada y sha256 verificado: si Hugging Face sirve otro archivo, falla.
Usado por el Dockerfile en build y también sirve en local:
    python scripts/descargar_modelo_onnx.py [directorio_destino]

Solo librería estándar (no requiere huggingface_hub).
"""
import os
import sys
import hashlib
import urllib.request

REPO = "intfloat/multilingual-e5-small"
REVISION = "614241f622f53c4eeff9890bdc4f31cfecc418b3"
ARCHIVOS = {
    # destino local: (ruta en el repo, sha256)
    "model.onnx": ("onnx/model.onnx",
                   "ca456c06b3a9505ddfd9131408916dd79290368331e7d76bb621f1cba6bc8665"),
    "tokenizer.json": ("onnx/tokenizer.json",
                       "0b44a9d7b51c3c62626640cda0e2c2f70fdacdc25bbbd68038369d14ebdf4c39"),
}
DESTINO_DEFECTO = "models/multilingual-e5-small"


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def descargar(destino: str) -> None:
    os.makedirs(destino, exist_ok=True)
    for nombre, (ruta, esperado) in ARCHIVOS.items():
        final = os.path.join(destino, nombre)
        if os.path.exists(final) and sha256(final) == esperado:
            print(f"✓ {nombre} ya existe y coincide")
            continue
        url = f"https://huggingface.co/{REPO}/resolve/{REVISION}/{ruta}"
        temporal = final + ".part"
        print(f"↓ {url}")
        urllib.request.urlretrieve(url, temporal)
        obtenido = sha256(temporal)
        if obtenido != esperado:
            os.remove(temporal)
            sys.exit(f"✗ sha256 no coincide para {nombre}: {obtenido} (esperado {esperado})")
        os.replace(temporal, final)
        print(f"✓ {nombre} ({os.path.getsize(final) / 1e6:.0f} MB) verificado")


if __name__ == "__main__":
    descargar(sys.argv[1] if len(sys.argv) > 1 else DESTINO_DEFECTO)
