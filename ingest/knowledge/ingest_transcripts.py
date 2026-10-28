"""Ingesta transcripciones en Supabase con limpieza, chunking y deduplicación."""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

from dotenv import load_dotenv
from supabase import Client, create_client

LOGGER = logging.getLogger(__name__)
TABLE_NAME = "knowledge_chunks_v2"
SUPPORTED_SUFFIXES = {".txt", ".md", ".json"}
DEFAULT_INPUT_DIR = Path("data/transcripciones/")
DOMAIN_PATTERN = re.compile(r"trading|marketing|negocio", re.IGNORECASE)
TIMESTAMP_PATTERN = re.compile(r"\[\d{2}:\d{2}:\d{2}(?:[.,]\d+)?\]")
FILLER_PATTERN = re.compile(r"\b(?:eh|ehm|em|mmm+|um+|ah)\b", re.IGNORECASE)
JSON_TEXT_KEYS = ("text", "texto", "transcript", "transcripcion", "content", "contenido")


@dataclass(frozen=True)
class FileResult:
    """Resumen de los chunks procesados para un archivo."""

    source_file: str
    domain: str
    chunks: int
    inserted: int
    updated: int
    total_chars: int
    total_words: int

    @property
    def average_chars(self) -> float:
        """Devuelve el tamaño promedio en caracteres."""
        return self.total_chars / self.chunks if self.chunks else 0.0

    @property
    def average_words(self) -> float:
        """Devuelve el tamaño promedio en palabras."""
        return self.total_words / self.chunks if self.chunks else 0.0


def extract_domain(file_path: Path) -> str:
    """Extrae trading, marketing o negocio de la subcarpeta; usa negocio por omisión."""
    match = DOMAIN_PATTERN.search(file_path.parent.name)
    return match.group(0).lower() if match else "negocio"


def clean_text(text: str) -> str:
    """Quita timestamps y muletillas, y conserva una sola separación entre párrafos."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = TIMESTAMP_PATTERN.sub(" ", text)
    text = FILLER_PATTERN.sub(" ", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    """Crea chunks de unas 500 palabras, con solape y sin cortar párrafos cortos.

    Los párrafos que superan por sí solos ``chunk_size`` se dividen por palabras.
    El solape se añade al inicio de cada chunk a partir del chunk anterior.
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size debe ser mayor que cero")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap debe ser no negativo y menor que chunk_size")
    if not text.strip():
        return []

    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
    base_chunks: list[str] = []
    current_parts: list[str] = []
    current_word_count = 0

    def flush_current() -> None:
        """Cierra el chunk base en construcción, si contiene texto."""
        nonlocal current_parts, current_word_count
        if current_parts:
            base_chunks.append("\n\n".join(current_parts))
            current_parts = []
            current_word_count = 0

    for paragraph in paragraphs:
        words = paragraph.split()
        if len(words) > chunk_size:
            flush_current()
            while len(words) > chunk_size:
                base_chunks.append(" ".join(words[:chunk_size]))
                words = words[chunk_size:]
            if words:
                current_parts = [" ".join(words)]
                current_word_count = len(words)
            continue

        if current_parts and current_word_count + len(words) > chunk_size:
            flush_current()
        current_parts.append(paragraph)
        current_word_count += len(words)

    flush_current()
    if not overlap:
        return base_chunks

    chunks = base_chunks[:1]
    for index in range(1, len(base_chunks)):
        previous_words = base_chunks[index - 1].split()
        prefix = " ".join(previous_words[-overlap:])
        chunks.append(f"{prefix}\n\n{base_chunks[index]}")
    return chunks


def _json_to_text(value: Any) -> str:
    """Extrae texto de estructuras JSON comunes de transcripciones."""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "\n".join(filter(None, (_json_to_text(item) for item in value)))
    if isinstance(value, dict):
        for key in JSON_TEXT_KEYS:
            if key in value:
                text = _json_to_text(value[key])
                if text:
                    return text
        return "\n".join(filter(None, (_json_to_text(item) for item in value.values())))
    return ""


def read_transcript(file_path: Path) -> str:
    """Lee un transcript TXT, Markdown o JSON como texto Unicode."""
    raw_text = file_path.read_text(encoding="utf-8-sig")
    if file_path.suffix.lower() != ".json":
        return raw_text
    return _json_to_text(json.loads(raw_text))


def transcript_files(input_dir: Path) -> Iterator[Path]:
    """Itera recursivamente los archivos soportados en orden determinista."""
    for file_path in sorted(input_dir.rglob("*")):
        if file_path.is_file() and file_path.suffix.lower() in SUPPORTED_SUFFIXES:
            yield file_path


def make_supabase_client() -> Client:
    """Crea el cliente con las credenciales de servicio definidas en .env."""
    load_dotenv()
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise RuntimeError("Faltan SUPABASE_URL o SUPABASE_SERVICE_ROLE_KEY en .env")
    return create_client(url, key)


def ingest_file(client: Client, file_path: Path, source_file: str) -> FileResult:
    """Inserta o actualiza los chunks de un archivo según (source_file, chunk_index)."""
    domain = extract_domain(file_path)
    chunks = chunk_text(clean_text(read_transcript(file_path)))
    existing_response = (
        client.table(TABLE_NAME)
        .select("chunk_index")
        .eq("source_file", source_file)
        .execute()
    )
    existing_indexes = {int(row["chunk_index"]) for row in existing_response.data or []}

    inserted = 0
    updated = 0
    for chunk_index, content in enumerate(chunks):
        payload = {
            "content": content,
            "source_file": source_file,
            "course_title": file_path.stem,
            "domain": domain,
            "chunk_index": chunk_index,
        }
        if chunk_index in existing_indexes:
            (
                client.table(TABLE_NAME)
                .update({
                    "content": content,
                    "course_title": file_path.stem,
                    "domain": domain,
                })
                .eq("source_file", source_file)
                .eq("chunk_index", chunk_index)
                .execute()
            )
            updated += 1
        else:
            client.table(TABLE_NAME).insert(payload).execute()
            inserted += 1

    return FileResult(
        source_file=source_file,
        domain=domain,
        chunks=len(chunks),
        inserted=inserted,
        updated=updated,
        total_chars=sum(len(content) for content in chunks),
        total_words=sum(len(content.split()) for content in chunks),
    )


def main() -> int:
    """Ejecuta la ingesta e imprime resultados por archivo y un resumen final."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    input_dir = args.input_dir.expanduser().resolve()
    if not input_dir.is_dir():
        parser.error(f"La carpeta de entrada no existe: {input_dir}")

    client = make_supabase_client()
    results: list[FileResult] = []
    errors: list[str] = []
    for file_path in transcript_files(input_dir):
        source_file = file_path.relative_to(input_dir).as_posix()
        try:
            result = ingest_file(client, file_path, source_file)
        except Exception as exc:  # Continúa con los demás archivos y resume los errores.
            LOGGER.error("Error procesando %s: %s", source_file, exc)
            errors.append(source_file)
            continue
        results.append(result)
        print(
            f"{result.source_file}: dominio={result.domain}, chunks={result.chunks}, "
            f"insertados={result.inserted}, actualizados={result.updated}, "
            f"tamaño promedio={result.average_chars:.1f} caracteres / "
            f"{result.average_words:.1f} palabras"
        )

    total_chunks = sum(result.chunks for result in results)
    total_chars = sum(result.total_chars for result in results)
    total_words = sum(result.total_words for result in results)
    average_chars = total_chars / total_chunks if total_chunks else 0.0
    average_words = total_words / total_chunks if total_chunks else 0.0
    print(
        f"Resumen: archivos={len(results)}, chunks={total_chunks}, "
        f"insertados={sum(result.inserted for result in results)}, "
        f"actualizados={sum(result.updated for result in results)}, "
        f"tamaño promedio={average_chars:.1f} caracteres / {average_words:.1f} palabras, "
        f"errores={len(errors)}"
    )
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
