"""
embeddings_onnx.py — Codifica texto con intfloat/multilingual-e5-small vía ONNX.

Reemplaza a sentence-transformers/torch en producción (Railway): solo necesita
onnxruntime + tokenizers + numpy. Produce los mismos vectores que
SentenceTransformer("intfloat/multilingual-e5-small") con normalize_embeddings=True
(mean pooling sobre la máscara de atención + normalización L2).

El modelo se baja con scripts/descargar_modelo_onnx.py (revisión fijada,
sha256 verificado). Ruta configurable con IKKI_EMBED_MODEL_DIR.
"""
import os
from functools import lru_cache

import numpy as np

MODEL_DIR = os.environ.get("IKKI_EMBED_MODEL_DIR", "models/multilingual-e5-small")
MAX_TOKENS = 512
PREFIJO_QUERY = "query: "
PREFIJO_PASAJE = "passage: "


@lru_cache(maxsize=1)
def _cargar():
    import onnxruntime as ort
    from tokenizers import Tokenizer

    modelo = os.path.join(MODEL_DIR, "model.onnx")
    tokenizer_path = os.path.join(MODEL_DIR, "tokenizer.json")
    if not (os.path.exists(modelo) and os.path.exists(tokenizer_path)):
        raise RuntimeError(f"Modelo ONNX no encontrado en {MODEL_DIR}. "
                           "Corre: python scripts/descargar_modelo_onnx.py")

    tokenizer = Tokenizer.from_file(tokenizer_path)
    tokenizer.enable_truncation(max_length=MAX_TOKENS)
    tokenizer.enable_padding(pad_id=tokenizer.token_to_id("<pad>"), pad_token="<pad>")

    opciones = ort.SessionOptions()
    opciones.intra_op_num_threads = int(os.environ.get("IKKI_EMBED_THREADS", "2"))
    sesion = ort.InferenceSession(modelo, opciones, providers=["CPUExecutionProvider"])
    entradas = {i.name for i in sesion.get_inputs()}
    return tokenizer, sesion, entradas


def codificar(textos: list[str]) -> np.ndarray:
    """Vectores normalizados (n, 384) float32. Los textos deben traer su prefijo."""
    tokenizer, sesion, entradas = _cargar()
    lote = tokenizer.encode_batch(textos)
    input_ids = np.array([e.ids for e in lote], dtype=np.int64)
    mascara = np.array([e.attention_mask for e in lote], dtype=np.int64)
    feed = {"input_ids": input_ids, "attention_mask": mascara}
    if "token_type_ids" in entradas:
        feed["token_type_ids"] = np.zeros_like(input_ids)

    ocultos = sesion.run(["last_hidden_state"], feed)[0]
    m = mascara[..., None].astype(np.float32)
    promedio = (ocultos * m).sum(axis=1) / np.clip(m.sum(axis=1), 1e-9, None)
    return (promedio / np.linalg.norm(promedio, axis=1, keepdims=True)).astype(np.float32)


def codificar_query(texto: str) -> np.ndarray:
    return codificar([PREFIJO_QUERY + texto])[0]


def a_pgvector(vector: np.ndarray) -> str:
    """Literal '[x1,x2,...]' que acepta una columna/argumento vector de pgvector."""
    return "[" + ",".join(f"{x:.7f}" for x in vector) + "]"
