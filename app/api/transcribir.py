import asyncio
import os
import tempfile
import urllib.request
from pathlib import Path
from typing import List, Tuple

from fastapi import APIRouter, HTTPException
from faster_whisper import WhisperModel
from pydantic import AliasChoices, BaseModel, Field

MODEL_NAME = os.getenv("WHISPER_MODEL", "small")
DEVICE = os.getenv("WHISPER_DEVICE", "cpu")
COMPUTE_TYPE = os.getenv("WHISPER_COMPUTE_TYPE", "int8")

model = WhisperModel(MODEL_NAME, device=DEVICE, compute_type=COMPUTE_TYPE)

router = APIRouter()


class TranscriptionRequest(BaseModel):
    url_o_ruta_audio: str = Field(
        validation_alias=AliasChoices("url_o_ruta_audio", "source")
    )


class Segment(BaseModel):
    start: float
    end: float
    text: str


class TranscriptionResponse(BaseModel):
    text: str
    segments: List[Segment]
    language: str
    language_probability: float
    duration: float


def _download_to_temp(url: str) -> str:
    suffix = Path(url.split("?")[0]).suffix or ".audio"
    fd, tmp_path = tempfile.mkstemp(suffix=suffix)
    os.close(fd)
    try:
        with urllib.request.urlopen(url, timeout=60) as response, open(tmp_path, "wb") as out:
            out.write(response.read())
    except Exception:
        os.unlink(tmp_path)
        raise
    return tmp_path


def _resolve_source(source: str) -> Tuple[str, bool]:
    if source.startswith(("http://", "https://")):
        return _download_to_temp(source), True
    path = os.path.expanduser(source)
    if not os.path.isfile(path):
        raise FileNotFoundError(f"No existe el archivo de audio: {source}")
    return path, False


def _transcribe_sync(source: str) -> dict:
    path, is_temp = _resolve_source(source)
    try:
        segments_iter, info = model.transcribe(path, language="es")
        segments = [
            {
                "start": round(segment.start, 2),
                "end": round(segment.end, 2),
                "text": segment.text.strip(),
            }
            for segment in segments_iter
        ]
        return {
            "text": " ".join(segment["text"] for segment in segments).strip(),
            "segments": segments,
            "language": info.language,
            "language_probability": round(info.language_probability, 4),
            "duration": round(info.duration, 2),
        }
    finally:
        if is_temp:
            try:
                os.unlink(path)
            except OSError:
                pass


@router.post("/transcribir", response_model=TranscriptionResponse)
async def transcribir(payload: TranscriptionRequest):
    try:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, _transcribe_sync, payload.url_o_ruta_audio
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error al transcribir: {exc}")
