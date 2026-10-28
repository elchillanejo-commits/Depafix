#!/usr/bin/env python3
"""Migra los RAG de trading y marketing al esquema nuevo de knowledge_chunks.

Fuentes (solo lectura):
  - trading:   Supabase knowledge_entries (fuente='video_txt' sin sub-chunks).
               Hoy no existe una tabla fragments en el esquema public.
  - marketing: Supabase knowledge_chunks (esquema viejo) + knowledge_entries,
               o data/conocimiento.db (tabla documentos) como fallback.

Destino:
  - knowledge_chunks_v2 con las columnas base domain, source_file,
    course_title, content, chunk_index y, si existen, entry_id, categoria y
    embedding. El esquema recomendado usa knowledge_chunks_v2 para no romper el
    RAG vectorial actual durante la migración.
    DDL: 07_IKKI_MARKETING/sql/10_knowledge_chunks_v2.sql

  - marketing copia los embeddings del esquema viejo (mismo modelo e5).
  - trading genera embeddings con ONNX (o sentence-transformers como fallback)
    solo si se pasa --embeddings.

Por defecto corre en dry-run. Para escribir: --apply.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sqlite3
import sys
import urllib.request
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SQLITE = ROOT / "data" / "conocimiento.db"
TARGET_COLUMNS = ("domain", "source_file", "course_title", "content", "chunk_index")
OPTIONAL_COLUMNS = ("entry_id", "categoria", "embedding")
COVERED_COLUMNS = TARGET_COLUMNS + OPTIONAL_COLUMNS
MODEL_NAME = "intfloat/multilingual-e5-small"
PREFIJO_PASAJE = "passage: "
EMBED_MODEL_DIR = ROOT / "models" / "multilingual-e5-small"
PAGE_SIZE = 1000
CHUNK_SUFFIX = re.compile(r"\s*\[\d+\s*/\s*\d+\]\s*$")

log = logging.getLogger("migrate_rags")


@dataclass(slots=True)
class Record:
    domain: str
    source_file: str | None
    course_title: str | None
    content: str
    chunk_index: int
    source: str
    source_id: str
    parent_id: int | None = None
    parent_chunk_index: int = 0
    sub_index: int = 0
    sort_order: int | None = None
    categoria: str | None = None
    embedding: str | None = None

    @property
    def key(self) -> str:
        return self.content.strip()[:100]

    def payload(self, columns: set[str] | None = None) -> dict[str, Any]:
        data: dict[str, Any] = {
            "domain": self.domain,
            "source_file": self.source_file,
            "course_title": self.course_title,
            "content": self.content,
            "chunk_index": self.chunk_index,
        }
        if columns is None or "entry_id" in columns:
            if self.parent_id is not None:
                data["entry_id"] = self.parent_id
        if columns is None or "categoria" in columns:
            if self.categoria is not None:
                data["categoria"] = self.categoria
        if self.embedding is not None and (columns is None or "embedding" in columns):
            data["embedding"] = self.embedding
        return data


def load_env() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    for path in (ROOT / ".env", Path.home() / ".depafix_secrets"):
        if path.exists():
            load_dotenv(path, override=False)


def parse_metadata(row: dict[str, Any]) -> dict[str, Any]:
    meta = row.get("metadata")
    if isinstance(meta, dict):
        return meta
    if isinstance(meta, str) and meta.strip():
        try:
            value = json.loads(meta)
            return value if isinstance(value, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def first_value(mapping: dict[str, Any], keys: Iterable[str]) -> Any:
    for key in keys:
        value = mapping.get(key)
        if value is not None and str(value).strip():
            return value
    return None


def as_int(value: Any, fallback: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def strip_chunk_suffix(title: Any) -> str | None:
    if not title:
        return None
    value = CHUNK_SUFFIX.sub("", str(title)).strip()
    return value or None


def source_file_from(meta: dict[str, Any], fallback: Any = None) -> str | None:
    value = first_value(meta, ("archivo", "source_file", "file", "filename"))
    if value is None:
        value = fallback
    if value is None or not str(value).strip():
        return None
    return str(value).strip()


def course_title_from(meta: dict[str, Any], title: Any, source_file: str | None) -> str | None:
    candidates = (
        meta.get("titulo"),
        meta.get("curso"),
        meta.get("course_title"),
        meta.get("course"),
        strip_chunk_suffix(title),
        Path(source_file).stem if source_file else None,
    )
    for candidate in candidates:
        if candidate is not None and str(candidate).strip():
            return str(candidate).strip()
    return None


def fetch_all(client: Any, table: str, select: str = "*", order: str | None = "id") -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    start = 0
    while True:
        query = client.table(table).select(select)
        if order:
            query = query.order(order)
        batch = query.range(start, start + PAGE_SIZE - 1).execute().data or []
        rows.extend(batch)
        if len(batch) < PAGE_SIZE:
            break
        start += PAGE_SIZE
    return rows


def fetch_openapi(url: str, key: str) -> dict[str, Any]:
    request = urllib.request.Request(
        url.rstrip("/") + "/rest/v1/",
        headers={
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Accept": "application/openapi+json",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def table_definitions(spec: dict[str, Any]) -> dict[str, Any]:
    return spec.get("definitions") or spec.get("components", {}).get("schemas") or {}


def target_status(spec: dict[str, Any], table: str) -> tuple[dict[str, Any] | None, list[str], list[str]]:
    definition = table_definitions(spec).get(table)
    if definition is None:
        return None, list(TARGET_COLUMNS), []
    props = definition.get("properties", {})
    missing = [column for column in TARGET_COLUMNS if column not in props]
    blocking = []
    for column in definition.get("required", []):
        if column in COVERED_COLUMNS:
            continue
        prop = props.get(column, {})
        if prop.get("default") is not None:
            continue
        if column == "id" or "Primary Key" in str(prop.get("description", "")):
            continue
        blocking.append(column)
    return definition, missing, blocking


def read_trading(entries: list[dict[str, Any]], marketing_entry_ids: set[int]) -> tuple[list[Record], int]:
    records: list[Record] = []
    skipped = 0
    for entry in entries:
        if entry.get("fuente") != "video_txt" or entry.get("id") in marketing_entry_ids:
            continue
        content = str(entry.get("contenido") or "").strip()
        if not content:
            skipped += 1
            continue
        meta = parse_metadata(entry)
        source_file = source_file_from(meta)
        records.append(
            Record(
                domain="trading",
                source_file=source_file,
                course_title=course_title_from(meta, entry.get("titulo"), source_file),
                content=content,
                chunk_index=0,
                source="knowledge_entries",
                source_id=str(entry.get("id")),
                parent_id=entry.get("id"),
                parent_chunk_index=as_int(meta.get("chunk_index"), len(records) + 1),
                sub_index=1,
                categoria=meta.get("categoria"),
            )
        )
    return records, skipped


def read_marketing_supabase(
    chunks: list[dict[str, Any]], entries_by_id: dict[int, dict[str, Any]]
) -> tuple[list[Record], int]:
    records: list[Record] = []
    skipped = 0
    for chunk in chunks:
        parent = entries_by_id.get(chunk.get("entry_id"))
        if parent is None:
            skipped += 1
            continue
        content = str(chunk.get("texto") or "").strip()
        if not content:
            skipped += 1
            continue
        meta = parse_metadata(parent)
        source_file = source_file_from(meta)
        embedding = chunk.get("embedding")
        if embedding is not None and not isinstance(embedding, str):
            embedding = str(embedding)
        records.append(
            Record(
                domain="marketing",
                source_file=source_file,
                course_title=course_title_from(meta, parent.get("titulo"), source_file),
                content=content,
                chunk_index=0,
                source="knowledge_chunks",
                source_id=str(chunk.get("id", len(records) + 1)),
                parent_id=chunk.get("entry_id"),
                parent_chunk_index=as_int(meta.get("chunk_index"), 0),
                sub_index=as_int(chunk.get("sub_index"), 1),
                categoria=chunk.get("categoria") or meta.get("categoria"),
                embedding=embedding,
            )
        )
    return records, skipped


def read_marketing_sqlite(path: Path) -> tuple[list[Record], int]:
    if not path.exists():
        raise FileNotFoundError(path)
    connection = sqlite3.connect(path)
    try:
        rows = connection.execute(
            "SELECT id, text, source, metadata FROM documentos ORDER BY id"
        ).fetchall()
    finally:
        connection.close()
    records: list[Record] = []
    skipped = 0
    for row_id, text, source, metadata in rows:
        content = str(text or "").strip()
        if not content:
            skipped += 1
            continue
        meta: dict[str, Any] = {}
        if metadata:
            try:
                value = json.loads(metadata)
                if isinstance(value, dict):
                    meta = value
            except json.JSONDecodeError:
                pass
        source_file = source_file_from(meta, fallback=source)
        faiss_id = meta.get("faiss_id")
        records.append(
            Record(
                domain="marketing",
                source_file=source_file,
                course_title=course_title_from(meta, None, source_file),
                content=content,
                chunk_index=0,
                source="documentos",
                source_id=str(row_id),
                parent_id=as_int(meta.get("parent_id"), 0) or None,
                parent_chunk_index=as_int(meta.get("chunk_index"), 0),
                sub_index=as_int(meta.get("sub_index"), 1),
                sort_order=int(faiss_id) if faiss_id is not None else None,
                categoria=meta.get("categoria"),
            )
        )
    return records, skipped


def read_fragments(client: Any, table: str = "fragments") -> tuple[list[Record], int]:
    rows = fetch_all(client, table, "*", order=None)
    records: list[Record] = []
    skipped = 0
    for index, row in enumerate(rows, 1):
        content = first_value(row, ("content", "texto", "contenido", "text", "fragment", "fragmento"))
        if content is None or not str(content).strip():
            skipped += 1
            continue
        domain = str(first_value(row, ("domain", "dominio")) or "trading").strip().lower()
        if domain not in {"trading", "marketing"}:
            domain = "trading"
        source_file = first_value(row, ("source_file", "archivo", "file", "filename", "fuente"))
        course_title = first_value(row, ("course_title", "curso", "titulo", "title", "course"))
        chunk_index = first_value(row, ("chunk_index", "sub_index", "orden", "indice", "index"))
        records.append(
            Record(
                domain=domain,
                source_file=str(source_file).strip() if source_file else None,
                course_title=str(course_title).strip() if course_title else None,
                content=str(content).strip(),
                chunk_index=0,
                source=table,
                source_id=str(row.get("id", index)),
                parent_id=as_int(first_value(row, ("entry_id", "parent_id")), 0) or None,
                sub_index=as_int(chunk_index, index),
                categoria=first_value(row, ("categoria", "category")),
            )
        )
    return records, skipped


def dedupe(records: list[Record]) -> tuple[list[Record], list[tuple[Record, Record]], int]:
    seen: dict[str, Record] = {}
    kept: list[Record] = []
    duplicates: list[tuple[Record, Record]] = []
    invalid = 0
    for record in records:
        key = record.key
        if not key:
            invalid += 1
            continue
        previous = seen.get(key)
        if previous is not None:
            duplicates.append((previous, record))
            continue
        seen[key] = record
        kept.append(record)
    return kept, duplicates, invalid


def assign_chunk_indexes(records: list[Record]) -> None:
    groups: dict[tuple[str, str | None], list[Record]] = {}
    for record in records:
        groups.setdefault((record.domain, record.source_file), []).append(record)
    for group in groups.values():
        group.sort(
            key=lambda record: (
                record.sort_order if record.sort_order is not None else 0,
                record.parent_chunk_index,
                record.sub_index,
                record.parent_id or 0,
                record.source_id,
            )
        )
        for index, record in enumerate(group, 1):
            record.chunk_index = index


def chunk_index_collisions(records: list[Record]) -> int:
    keys = Counter((record.domain, record.source_file, record.chunk_index) for record in records)
    return sum(count - 1 for count in keys.values() if count > 1)


def generate_embeddings(records: list[Record], batch_size: int) -> tuple[int, str]:
    pending = [record for record in records if not record.embedding]
    if not pending:
        return 0, "nada pendiente"

    onnx_model = EMBED_MODEL_DIR / "model.onnx"
    onnx_tokenizer = EMBED_MODEL_DIR / "tokenizer.json"
    if onnx_model.exists() and onnx_tokenizer.exists():
        os.environ.setdefault("IKKI_EMBED_MODEL_DIR", str(EMBED_MODEL_DIR))
        sys.path.insert(0, str(ROOT))
        from src.agencia.embeddings_onnx import a_pgvector, codificar

        modo = "onnx"
        for start in range(0, len(pending), batch_size):
            batch = pending[start:start + batch_size]
            vectors = codificar([PREFIJO_PASAJE + record.content for record in batch])
            for record, vector in zip(batch, vectors):
                record.embedding = a_pgvector(vector)
            log.info(
                "Embeddings %d/%d (%s)",
                min(start + batch_size, len(pending)),
                len(pending),
                modo,
            )
        return len(pending), modo

    from sentence_transformers import SentenceTransformer

    modelo = SentenceTransformer(MODEL_NAME)
    modo = "sentence-transformers"
    for start in range(0, len(pending), batch_size):
        batch = pending[start:start + batch_size]
        vectors = modelo.encode(
            [PREFIJO_PASAJE + record.content for record in batch],
            normalize_embeddings=True,
            batch_size=batch_size,
            show_progress_bar=False,
        )
        for record, vector in zip(batch, vectors):
            record.embedding = "[" + ",".join(f"{x:.7f}" for x in vector) + "]"
        log.info(
            "Embeddings %d/%d (%s)",
            min(start + batch_size, len(pending)),
            len(pending),
            modo,
        )
    return len(pending), modo


def read_existing_keys(client: Any, table: str, spec: dict[str, Any]) -> set[str]:
    definition = table_definitions(spec).get(table)
    if definition is None or "content" not in definition.get("properties", {}):
        return set()
    try:
        rows = fetch_all(client, table, "content")
    except Exception as exc:
        log.debug("No se pudo leer content existente en %s: %s", table, exc)
        return set()
    return {
        str(row.get("content") or "").strip()[:100]
        for row in rows
        if str(row.get("content") or "").strip()
    }


def insert_records(
    client: Any,
    table: str,
    records: list[Record],
    batch_size: int,
    columns: set[str] | None,
) -> int:
    inserted = 0
    for start in range(0, len(records), batch_size):
        batch = [
            record.payload(columns) for record in records[start:start + batch_size]
        ]
        client.table(table).insert(batch).execute()
        inserted += len(batch)
        log.info("Insertados %d/%d", inserted, len(records))
    return inserted


def print_report(
    args: argparse.Namespace,
    entries_count: int,
    trading_records: list[Record],
    marketing_records: list[Record],
    trading_skipped: int,
    marketing_skipped: int,
    kept: list[Record],
    duplicates: list[tuple[Record, Record]],
    invalid: int,
    existing_skipped: int,
    definition: dict[str, Any] | None,
    missing: list[str],
    blocking: list[str],
) -> None:
    mode = "APPLY" if args.apply else "DRY-RUN"
    cross = sum(1 for previous, current in duplicates if previous.domain != current.domain)
    intra = len(duplicates) - cross
    counts = Counter(record.domain for record in kept)
    print(f"\n{mode} — migración de RAGs a {args.target_table}")
    print(f"knowledge_entries leídas: {entries_count}")
    print(f"trading:   {len(trading_records)} registros ({trading_skipped} omitidos)")
    print(f"marketing: {len(marketing_records)} registros ({marketing_skipped} omitidos)")
    print(f"duplicados: {len(duplicates)} (entre fuentes: {cross}, intra-fuente: {intra})")
    print(f"inválidos (content vacío): {invalid}")
    print(f"ya existentes en destino: {existing_skipped}")
    print(f"colisiones (domain, source_file, chunk_index): {chunk_index_collisions(kept)}")
    print(f"a insertar: {len(kept)} (trading={counts['trading']}, marketing={counts['marketing']})")
    with_embedding = sum(1 for record in kept if record.embedding)
    print(f"con embedding: {with_embedding}/{len(kept)}")
    if definition is not None:
        props = definition.get("properties", {})
        extra_present = [column for column in OPTIONAL_COLUMNS if column in props]
        extra_missing = [column for column in OPTIONAL_COLUMNS if column not in props]
        print(f"columnas extra destino: {extra_present or 'ninguna'}")
        if extra_missing:
            print(f"columnas extra ausentes: {extra_missing} (se omiten)")
    if definition is None:
        print(f"destino {args.target_table}: NO existe (apply bloqueado)")
    elif missing:
        print(f"destino {args.target_table}: faltan columnas {missing} (apply bloqueado)")
    elif blocking:
        print(f"destino {args.target_table}: columnas requeridas no cubiertas {blocking} (apply bloqueado)")
    else:
        print(f"destino {args.target_table}: esquema nuevo OK")
    if duplicates:
        print("\nDuplicados detectados (content[:100], se conserva el primero):")
        for previous, current in duplicates[:args.max_duplicates]:
            print(
                f"  - {previous.domain}/{previous.source}:{previous.source_id}"
                f"  <->  {current.domain}/{current.source}:{current.source_id}"
                f"  :: {current.key!r}"
            )
        if len(duplicates) > args.max_duplicates:
            print(f"  ... y {len(duplicates) - args.max_duplicates} más")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Solo reporta; no escribe (default)")
    mode.add_argument("--apply", action="store_true", help="Inserta en la tabla destino")
    parser.add_argument(
        "--target-table",
        default=os.getenv("KNOWLEDGE_TARGET_TABLE", "knowledge_chunks_v2"),
        help="Tabla destino (default: knowledge_chunks_v2)",
    )
    parser.add_argument(
        "--marketing-source",
        choices=("auto", "supabase", "sqlite"),
        default="auto",
        help="Origen del RAG de marketing (default: auto)",
    )
    parser.add_argument(
        "--marketing-sqlite",
        type=Path,
        default=DEFAULT_SQLITE,
        help=f"SQLite de respaldo para marketing (default: {DEFAULT_SQLITE})",
    )
    parser.add_argument(
        "--trading-source",
        choices=("auto", "knowledge_entries", "fragments"),
        default="auto",
        help="Origen del RAG de trading (default: auto)",
    )
    parser.add_argument(
        "--skip-existing",
        dest="skip_existing",
        action="store_true",
        default=True,
        help="No reinsertar content ya presente en destino (default)",
    )
    parser.add_argument(
        "--no-skip-existing",
        dest="skip_existing",
        action="store_false",
        help="Insertar aunque el content ya exista en destino",
    )
    parser.add_argument("--batch-size", type=int, default=200, help="Filas por insert (default: 200)")
    parser.add_argument(
        "--embeddings",
        action="store_true",
        help="Genera embeddings faltantes (trading y fallback SQLite); marketing copia los del esquema viejo",
    )
    parser.add_argument(
        "--embedding-batch-size",
        type=int,
        default=16,
        help="Textos por lote al generar embeddings (default: 16)",
    )
    parser.add_argument(
        "--allow-null-embeddings",
        action="store_true",
        help="Permite insertar filas sin embedding (el RPC no las recuperará)",
    )
    parser.add_argument(
        "--max-duplicates",
        type=int,
        default=25,
        help="Cuántos duplicados listar (default: 25)",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )
    load_env()

    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        log.error("Faltan SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY")
        return 2

    from supabase import create_client

    client = create_client(url, key)
    spec = fetch_openapi(url, key)
    tables = set(table_definitions(spec))

    log.info("Leyendo knowledge_entries...")
    entries = fetch_all(client, "knowledge_entries", "id,fuente,titulo,contenido,metadata")
    entries_by_id = {entry["id"]: entry for entry in entries}
    log.info("knowledge_entries: %d filas", len(entries))

    chunks: list[dict[str, Any]] | None = None
    try:
        chunks = fetch_all(
            client,
            "knowledge_chunks",
            "id,entry_id,sub_index,texto,categoria,embedding",
        )
        log.info("knowledge_chunks (esquema viejo): %d filas", len(chunks))
    except Exception as exc:
        log.warning("No se pudo leer knowledge_chunks viejo: %s", exc)

    marketing_records: list[Record] = []
    marketing_skipped = 0
    if args.marketing_source in ("auto", "supabase") and chunks is not None:
        marketing_records, marketing_skipped = read_marketing_supabase(chunks, entries_by_id)
        log.info("Marketing desde Supabase: %d registros", len(marketing_records))
    if args.marketing_source == "supabase" and chunks is None:
        log.error("No se pudo leer knowledge_chunks viejo y --marketing-source=supabase")
        return 2
    if args.marketing_source == "sqlite" or (args.marketing_source == "auto" and not marketing_records):
        log.info("Marketing desde SQLite: %s", args.marketing_sqlite)
        try:
            marketing_records, marketing_skipped = read_marketing_sqlite(args.marketing_sqlite)
        except Exception as exc:
            log.error("No se pudo leer %s: %s", args.marketing_sqlite, exc)
            return 2

    marketing_entry_ids = {
        record.parent_id for record in marketing_records if record.parent_id is not None
    }
    trading_records: list[Record] = []
    trading_skipped = 0
    if args.trading_source == "fragments" and "fragments" not in tables:
        log.error("Se pidió --trading-source=fragments pero la tabla no existe")
        return 2
    if args.trading_source in ("auto", "fragments") and "fragments" in tables:
        log.info("Trading desde tabla fragments")
        trading_records, trading_skipped = read_fragments(client)
        if not trading_records and args.trading_source == "auto":
            log.warning("fragments vacío; se usa knowledge_entries")
            trading_records, trading_skipped = read_trading(entries, marketing_entry_ids)
    else:
        log.info("Trading desde knowledge_entries")
        trading_records, trading_skipped = read_trading(entries, marketing_entry_ids)

    kept, duplicates, invalid = dedupe(trading_records + marketing_records)
    existing_skipped = 0
    if args.skip_existing:
        existing_keys = read_existing_keys(client, args.target_table, spec)
        before = len(kept)
        kept = [record for record in kept if record.key not in existing_keys]
        existing_skipped = before - len(kept)

    assign_chunk_indexes(kept)
    if args.embeddings:
        generated, embedding_mode = generate_embeddings(kept, args.embedding_batch_size)
        log.info("Embeddings generados: %d (%s)", generated, embedding_mode)
    definition, missing, blocking = target_status(spec, args.target_table)
    print_report(
        args,
        len(entries),
        trading_records,
        marketing_records,
        trading_skipped,
        marketing_skipped,
        kept,
        duplicates,
        invalid,
        existing_skipped,
        definition,
        missing,
        blocking,
    )

    if not args.apply:
        print("\n(dry-run: no se escribió nada. Usa --apply cuando el esquema destino esté listo.)")
        return 0

    if definition is None:
        log.error("La tabla destino %s no existe", args.target_table)
        return 2
    if missing:
        log.error("Faltan columnas nuevas en %s: %s", args.target_table, missing)
        return 2
    if blocking:
        log.error(
            "La tabla %s exige columnas no incluidas en el payload: %s",
            args.target_table,
            blocking,
        )
        return 2
    if not kept:
        log.info("Nada que insertar")
        return 0

    missing_source = sum(1 for record in kept if not record.source_file)
    if missing_source:
        log.error("%d registros no tienen source_file", missing_source)
        return 2

    target_columns = set(definition.get("properties", {}))
    if "embedding" in target_columns:
        missing_embeddings = sum(1 for record in kept if not record.embedding)
        if missing_embeddings and not args.allow_null_embeddings:
            log.error(
                "%d registros no tienen embedding; usa --embeddings o --allow-null-embeddings",
                missing_embeddings,
            )
            return 2
    if "entry_id" in target_columns and "entry_id" in definition.get("required", []):
        missing_parents = sum(1 for record in kept if record.parent_id is None)
        if missing_parents:
            log.error("%d registros no tienen entry_id", missing_parents)
            return 2

    inserted = insert_records(
        client,
        args.target_table,
        kept,
        args.batch_size,
        target_columns,
    )
    log.info("Migración completa: %d registros insertados", inserted)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
