"""Carga y valida mapping_serviu.yaml contra base_schema.json al arranque.

Fail-fast: si la config es inválida, SystemExit(1) — el contenedor no arranca.
"""
from __future__ import annotations

import json
import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict

log = logging.getLogger(__name__)

MAPPING_FILENAME = "mapping_serviu.yaml"
SCHEMA_FILENAME = "base_schema.json"


def _config_dir() -> Path:
    override = os.environ.get("DEPA_CONFIG_DIR")
    if override:
        return Path(override).expanduser().resolve()
    return Path(__file__).resolve().parents[1] / "config"


class ConfigError(RuntimeError):
    """Config inválida. El bootstrap lo convierte en SystemExit(1)."""


class CampoMapping(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    tipo: str
    obligatorio: bool
    fuente: str


class MappingServiu(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    version: int
    campos: dict[str, CampoMapping]


def _load_yaml(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except FileNotFoundError as e:
        raise ConfigError(f"no existe {path}") from e
    except yaml.YAMLError as e:
        raise ConfigError(f"YAML inválido en {path}: {e}") from e


def _load_json(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError as e:
        raise ConfigError(f"no existe {path}") from e
    except json.JSONDecodeError as e:
        raise ConfigError(f"JSON inválido en {path}: {e}") from e


def _json_type_ok(data: Any, t: str) -> bool:
    return {
        "object":  lambda d: isinstance(d, dict),
        "array":   lambda d: isinstance(d, list),
        "string":  lambda d: isinstance(d, str),
        "integer": lambda d: isinstance(d, int) and not isinstance(d, bool),
        "number":  lambda d: isinstance(d, (int, float)) and not isinstance(d, bool),
        "boolean": lambda d: isinstance(d, bool),
        "null":    lambda d: d is None,
    }.get(t, lambda _: True)(data)


def _validate_jsonschema(data: Any, schema: dict, path: str) -> None:
    t = schema.get("type")
    if t and not _json_type_ok(data, t):
        raise ConfigError(f"{path}: tipo '{t}' esperado, recibido {type(data).__name__}")
    if isinstance(data, dict):
        for req in schema.get("required", []):
            if req not in data:
                raise ConfigError(f"{path}: falta clave requerida '{req}'")
        props = schema.get("properties", {})
        for k, v in data.items():
            if k in props:
                _validate_jsonschema(v, props[k], f"{path}.{k}")
            elif "additionalProperties" in schema and isinstance(schema["additionalProperties"], dict):
                _validate_jsonschema(v, schema["additionalProperties"], f"{path}.{k}")
            elif schema.get("additionalProperties") is False:
                raise ConfigError(f"{path}: clave no permitida '{k}'")
    if isinstance(data, list) and "items" in schema:
        for i, item in enumerate(data):
            _validate_jsonschema(item, schema["items"], f"{path}[{i}]")


@lru_cache(maxsize=1)
def get_mapping() -> MappingServiu:
    """Retorna el mapping validado y cacheado. Falla con ConfigError si es inválido."""
    cfg = _config_dir()
    raw = _load_yaml(cfg / MAPPING_FILENAME)
    schema = _load_json(cfg / SCHEMA_FILENAME)

    if not isinstance(raw, dict):
        raise ConfigError(
            f"{MAPPING_FILENAME}: raíz debe ser mapping, recibido {type(raw).__name__}"
        )
    _validate_jsonschema(raw, schema, "$")
    try:
        return MappingServiu(**raw)
    except Exception as e:
        raise ConfigError(f"validación Pydantic falló: {e}") from e


def _bootstrap() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    try:
        get_mapping()
    except ConfigError as e:
        log.critical("CONFIG INVALIDA — abortando arranque: %s", e)
        raise SystemExit(1) from e
    log.info("config OK: %s validado", MAPPING_FILENAME)


_bootstrap()
