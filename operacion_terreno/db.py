from __future__ import annotations

import calendar
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    create_engine,
    func,
    select,
    text,
)
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.mutable import MutableList
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship
from sqlalchemy.schema import CreateIndex, CreateTable

JSON_TYPE = JSON().with_variant(JSONB, "postgresql")
LIST_TYPE = MutableList.as_mutable(JSON().with_variant(JSONB, "postgresql"))


class Base(DeclarativeBase):
    pass


EstadoVisita = Enum(
    "PENDIENTE",
    "REALIZADA",
    "NO_ACCESO",
    "REPROGRAMADA",
    "CANCELADA",
    "NO_APLICA",
    name="estado_visita",
    native_enum=False,
    create_constraint=True,
    validate_strings=True,
)
TipoAguaCaliente = Enum(
    "TERMO_ELECTRICO",
    "CALEFONT",
    "CALDERA_CENTRAL",
    "SIN_INFORMACION",
    name="tipo_agua_caliente",
    native_enum=False,
    create_constraint=True,
    validate_strings=True,
)
EstadoPresupuesto = Enum(
    "BORRADOR",
    "SIMULACION_CORREDOR",
    "ENVIADO",
    "APROBADO",
    "RECHAZADO",
    "VENCIDO",
    name="estado_presupuesto",
    native_enum=False,
    create_constraint=True,
    validate_strings=True,
)
CanalComunicacion = Enum(
    "WHATSAPP",
    "LLAMADA",
    "EMAIL",
    "PRESENCIAL",
    name="canal_comunicacion",
    native_enum=False,
    create_constraint=True,
    validate_strings=True,
)
DireccionComunicacion = Enum(
    "SALIENTE",
    "ENTRANTE",
    name="direccion_comunicacion",
    native_enum=False,
    create_constraint=True,
    validate_strings=True,
)
EstadoMedicion = Enum(
    "MEDIDO",
    "PENDIENTE_MEDICION",
    name="estado_medicion",
    native_enum=False,
    create_constraint=True,
    validate_strings=True,
)
SyncStatus = Enum(
    "NO_SINCRONIZADO",
    "SINCRONIZADO",
    "ERROR",
    name="sync_status",
    native_enum=False,
    create_constraint=True,
    validate_strings=True,
)
EstadoContacto = Enum(
    "PENDIENTE",
    "ENVIADO",
    "RESPONDIDO",
    "SIN_RESPUESTA",
    "AGENDADO",
    "RECHAZADO",
    "CERRADO",
    name="estado_contacto",
    native_enum=False,
    create_constraint=True,
    validate_strings=True,
)


def calcular_proxima_mantencion(fecha_ultima: date, intervalo_meses: int) -> date:
    if intervalo_meses not in (6, 12):
        raise ValueError("El intervalo de mantención debe ser 6 o 12 meses.")
    total_meses = fecha_ultima.month - 1 + intervalo_meses
    anio = fecha_ultima.year + total_meses // 12
    mes = total_meses % 12 + 1
    dia = min(fecha_ultima.day, calendar.monthrange(anio, mes)[1])
    return date(anio, mes, dia)


class InspeccionTerreno(Base):
    __tablename__ = "inspecciones_terreno"
    __table_args__ = (
        CheckConstraint(
            "intervalo_mantencion_meses IS NULL OR intervalo_mantencion_meses IN (6, 12)",
            name="ck_inspeccion_intervalo_mantencion",
        ),
        CheckConstraint(
            "m2_piso_spc IS NULL OR m2_piso_spc >= 0",
            name="ck_inspeccion_m2_spc",
        ),
        CheckConstraint("plafones_led >= 0", name="ck_inspeccion_plafones"),
        CheckConstraint("enchufes >= 0", name="ck_inspeccion_enchufes"),
        CheckConstraint("soporte_tv >= 0", name="ck_inspeccion_soporte_tv"),
        CheckConstraint(
            "superficie_util_m2 IS NULL OR superficie_util_m2 >= 0",
            name="ck_inspeccion_superficie",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    propiedad_id: Mapped[str] = mapped_column(String(32), index=True)
    direccion: Mapped[str] = mapped_column(String(255))
    direccion_base: Mapped[str | None] = mapped_column(String(255), index=True, nullable=True)
    estado_propiedad: Mapped[str | None] = mapped_column(String(20), nullable=True)
    es_vacante: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    departamento: Mapped[str | None] = mapped_column(String(32), nullable=True)
    torre: Mapped[str | None] = mapped_column(String(16), nullable=True)
    comuna: Mapped[str] = mapped_column(String(80), default="Santiago", server_default=text("'Santiago'"))
    bloque: Mapped[str | None] = mapped_column(String(32), nullable=True)
    segmento_ruta: Mapped[str | None] = mapped_column(String(16), nullable=True)
    parada_ruta: Mapped[int | None] = mapped_column(Integer, nullable=True)
    superficie_util_m2: Mapped[float | None] = mapped_column(Numeric(8, 2), nullable=True)
    dormitorios: Mapped[int | None] = mapped_column(Integer, nullable=True)
    banos: Mapped[int | None] = mapped_column(Integer, nullable=True)
    prioridad_ready_to_rent: Mapped[str | None] = mapped_column(String(2), nullable=True)
    score_ready_to_rent: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fecha_inspeccion: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    inspector: Mapped[str | None] = mapped_column(String(120), nullable=True)
    estado_visita: Mapped[str] = mapped_column(
        EstadoVisita,
        default="PENDIENTE",
        server_default=text("'PENDIENTE'"),
        nullable=False,
    )
    tipo_agua_caliente: Mapped[str] = mapped_column(
        TipoAguaCaliente,
        default="SIN_INFORMACION",
        server_default=text("'SIN_INFORMACION'"),
        nullable=False,
    )
    fecha_ultima_mantencion_termo: Mapped[date | None] = mapped_column(Date, nullable=True)
    fecha_proxima_mantencion_termo: Mapped[date | None] = mapped_column(Date, nullable=True)
    intervalo_mantencion_meses: Mapped[int | None] = mapped_column(Integer, nullable=True)
    requiere_piso_spc: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    m2_piso_spc: Mapped[float | None] = mapped_column(Numeric(8, 2), nullable=True)
    plafones_led: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    enchufes: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    soporte_tv: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    fotos_antes: Mapped[list[str]] = mapped_column(LIST_TYPE, default=list, nullable=False)
    fotos_despues: Mapped[list[str]] = mapped_column(LIST_TYPE, default=list, nullable=False)
    videos_antes: Mapped[list[str]] = mapped_column(LIST_TYPE, default=list, nullable=False)
    videos_despues: Mapped[list[str]] = mapped_column(LIST_TYPE, default=list, nullable=False)
    observaciones: Mapped[str | None] = mapped_column(Text, nullable=True)
    latitud: Mapped[float | None] = mapped_column(Numeric(10, 6), nullable=True)
    longitud: Mapped[float | None] = mapped_column(Numeric(10, 6), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    presupuestos: Mapped[list["PresupuestoObra"]] = relationship(
        back_populates="inspeccion", cascade="all, delete-orphan"
    )
    comunicaciones: Mapped[list["LogComunicacionCorredor"]] = relationship(
        back_populates="inspeccion", cascade="all, delete-orphan"
    )


class PresupuestoObra(Base):
    __tablename__ = "presupuestos_obra"
    __table_args__ = (
        CheckConstraint("neto >= 0", name="ck_presupuesto_neto"),
        CheckConstraint("iva >= 0", name="ck_presupuesto_iva"),
        CheckConstraint("total >= 0", name="ck_presupuesto_total"),
        CheckConstraint("costo_mayorista >= 0", name="ck_presupuesto_costo"),
        CheckConstraint("comision_corredor >= 0", name="ck_presupuesto_comision"),
        CheckConstraint("margen_depafix >= 0", name="ck_presupuesto_margen"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    inspeccion_id: Mapped[int] = mapped_column(
        ForeignKey("inspecciones_terreno.id", ondelete="CASCADE"), index=True
    )
    propiedad_id: Mapped[str] = mapped_column(String(32), index=True)
    fecha_emision: Mapped[date | None] = mapped_column(Date, nullable=True)
    estado: Mapped[str] = mapped_column(
        EstadoPresupuesto,
        default="BORRADOR",
        server_default=text("'BORRADOR'"),
        nullable=False,
    )
    moneda: Mapped[str] = mapped_column(String(8), default="CLP", server_default=text("'CLP'"))
    neto: Mapped[float] = mapped_column(Numeric(12, 2), default=0, server_default=text("0"))
    iva: Mapped[float] = mapped_column(Numeric(12, 2), default=0, server_default=text("0"))
    total: Mapped[float] = mapped_column(Numeric(12, 2), default=0, server_default=text("0"))
    partidas: Mapped[list[dict[str, Any]]] = mapped_column(LIST_TYPE, default=list, nullable=False)
    costo_mayorista: Mapped[float] = mapped_column(Numeric(12, 2), default=0, server_default=text("0"))
    comision_corredor: Mapped[float] = mapped_column(Numeric(12, 2), default=0, server_default=text("0"))
    margen_depafix: Mapped[float] = mapped_column(Numeric(12, 2), default=0, server_default=text("0"))
    estado_medicion: Mapped[str] = mapped_column(
        EstadoMedicion,
        default="PENDIENTE_MEDICION",
        server_default=text("'PENDIENTE_MEDICION'"),
        nullable=False,
    )
    payload_json: Mapped[dict[str, Any] | None] = mapped_column(JSON_TYPE, nullable=True)
    uuid_railway: Mapped[str | None] = mapped_column(String(64), unique=True, index=True, nullable=True)
    sync_status: Mapped[str] = mapped_column(
        SyncStatus,
        default="NO_SINCRONIZADO",
        server_default=text("'NO_SINCRONIZADO'"),
        nullable=False,
    )
    synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sync_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    railway_response: Mapped[dict[str, Any] | None] = mapped_column(JSON_TYPE, nullable=True)
    pdf_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    observaciones: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    inspeccion: Mapped[InspeccionTerreno] = relationship(back_populates="presupuestos")


class LogComunicacionCorredor(Base):
    __tablename__ = "log_comunicaciones_corredor"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    propiedad_id: Mapped[str] = mapped_column(String(32), index=True)
    inspeccion_id: Mapped[int | None] = mapped_column(
        ForeignKey("inspecciones_terreno.id", ondelete="SET NULL"), index=True, nullable=True
    )
    canal: Mapped[str] = mapped_column(CanalComunicacion, nullable=False)
    direccion: Mapped[str] = mapped_column(
        DireccionComunicacion,
        default="SALIENTE",
        server_default=text("'SALIENTE'"),
        nullable=False,
    )
    estado_contacto: Mapped[str] = mapped_column(
        EstadoContacto,
        default="PENDIENTE",
        server_default=text("'PENDIENTE'"),
        nullable=False,
    )
    fecha_contacto: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    mensaje: Mapped[str | None] = mapped_column(Text, nullable=True)
    proximo_seguimiento: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    responsable: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    inspeccion: Mapped[InspeccionTerreno | None] = relationship(back_populates="comunicaciones")


def _sqlite_columns(conn, table: str) -> set[str]:
    return {row[1] for row in conn.exec_driver_sql(f"PRAGMA table_info({table})")}


def _migrate_sqlite_schema(engine) -> None:
    """Migra bases SQLite creadas con el esquema anterior sin perder datos."""
    if engine.dialect.name != "sqlite":
        return

    with engine.begin() as conn:
        tables = {
            row[0]
            for row in conn.exec_driver_sql(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }

        if "inspecciones_terreno" in tables:
            columns = _sqlite_columns(conn, "inspecciones_terreno")
            additions = {
                "direccion_base": "VARCHAR(255)",
                "estado_propiedad": "VARCHAR(20)",
                "es_vacante": "BOOLEAN DEFAULT 0 NOT NULL",
                "superficie_util_m2": "NUMERIC(8, 2)",
                "dormitorios": "INTEGER",
                "banos": "INTEGER",
                "prioridad_ready_to_rent": "VARCHAR(2)",
                "score_ready_to_rent": "INTEGER",
            }
            for name, ddl in additions.items():
                if name not in columns:
                    conn.exec_driver_sql(
                        f"ALTER TABLE inspecciones_terreno ADD COLUMN {name} {ddl}"
                    )
            conn.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS ix_inspecciones_terreno_direccion_base "
                "ON inspecciones_terreno (direccion_base)"
            )

        if "presupuestos_obra" in tables:
            columns = _sqlite_columns(conn, "presupuestos_obra")
            table_sql = conn.exec_driver_sql(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name='presupuestos_obra'"
            ).scalar() or ""
            required = {
                "costo_mayorista",
                "comision_corredor",
                "margen_depafix",
                "estado_medicion",
                "payload_json",
                "uuid_railway",
                "sync_status",
                "synced_at",
                "sync_error",
                "railway_response",
            }
            if "SIMULACION_CORREDOR" not in table_sql or required - columns:
                row_count = conn.exec_driver_sql(
                    "SELECT COUNT(*) FROM presupuestos_obra"
                ).scalar() or 0
                if row_count == 0:
                    conn.exec_driver_sql("DROP TABLE presupuestos_obra")
                    PresupuestoObra.__table__.create(conn)
                else:
                    conn.exec_driver_sql(
                        "ALTER TABLE presupuestos_obra RENAME TO presupuestos_obra_legacy"
                    )
                    PresupuestoObra.__table__.create(conn)
                    copy_columns = [
                        column.name
                        for column in PresupuestoObra.__table__.columns
                        if column.name in columns
                    ]
                    column_sql = ", ".join(f'"{name}"' for name in copy_columns)
                    conn.exec_driver_sql(
                        f"INSERT INTO presupuestos_obra ({column_sql}) "
                        f"SELECT {column_sql} FROM presupuestos_obra_legacy"
                    )
                    conn.exec_driver_sql("DROP TABLE presupuestos_obra_legacy")


def init_db(database_url: str):
    engine = create_engine(database_url, future=True)
    _migrate_sqlite_schema(engine)
    Base.metadata.create_all(engine)
    return engine


def _to_float(value: Any) -> float | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    try:
        if pd.isna(value):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value: Any) -> int | None:
    number = _to_float(value)
    return int(number) if number is not None else None


def seed_pending_inspections(engine, df: pd.DataFrame) -> dict[str, int]:
    with Session(engine) as session:
        existing = {
            row.propiedad_id: row for row in session.scalars(select(InspeccionTerreno))
        }
        inserted = 0
        updated = 0
        for _, row in df.iterrows():
            propiedad_id = str(row["id"])
            es_admin = bool(row["es_administracion"])
            instance = existing.get(propiedad_id)
            if instance is None:
                instance = InspeccionTerreno(
                    propiedad_id=propiedad_id,
                    estado_visita="NO_APLICA" if es_admin else "PENDIENTE",
                    tipo_agua_caliente="SIN_INFORMACION",
                )
                session.add(instance)
                inserted += 1
            else:
                updated += 1

            parada = row.get("parada_ruta")
            parada_int = int(parada) if pd.notna(parada) else None
            prioridad = str(row.get("prioridad_ready_to_rent") or "")
            instance.direccion = str(row["direccion_normalizada"])
            instance.direccion_base = (
                None if es_admin else (None if pd.isna(row.get("direccion_base")) else str(row["direccion_base"]))
            )
            instance.estado_propiedad = str(row["estado"])
            instance.es_vacante = bool(row["es_vacante"]) and not es_admin
            instance.departamento = None if pd.isna(row["departamento"]) else str(row["departamento"])
            instance.torre = None if pd.isna(row["torre"]) else str(row["torre"])
            instance.comuna = "Santiago"
            instance.bloque = None if pd.isna(row["bloque"]) else str(row["bloque"])
            instance.segmento_ruta = (
                None if es_admin or pd.isna(row.get("segmento_ruta")) else str(row["segmento_ruta"])
            )
            instance.parada_ruta = parada_int
            instance.superficie_util_m2 = None if es_admin else _to_float(row["superficie_util_m2"])
            instance.dormitorios = None if es_admin else _to_int(row["dormitorios"])
            instance.banos = None if es_admin else _to_int(row["banos"])
            instance.prioridad_ready_to_rent = prioridad if prioridad in {"A", "B", "C"} else None
            instance.score_ready_to_rent = 0 if es_admin else _to_int(row["score_ready_to_rent"])
            instance.observaciones = str(row["observaciones"]) if row["observaciones"] else None
            instance.latitud = _to_float(row.get("lat"))
            instance.longitud = _to_float(row.get("lon"))

            if (
                instance.fecha_inspeccion is None
                and not instance.requiere_piso_spc
                and instance.plafones_led == 0
                and instance.enchufes == 0
                and instance.soporte_tv == 0
            ):
                instance.requiere_piso_spc = bool(row["es_vacante"]) and not es_admin
                instance.plafones_led = _to_int(row.get("plafones_led_sugeridos")) or 0
                instance.enchufes = _to_int(row.get("enchufes_sugeridos")) or 0
                instance.soporte_tv = _to_int(row.get("soporte_tv_sugerido")) or 0

        session.commit()
    return {"insertadas": inserted, "actualizadas": updated}


def generate_postgres_ddl(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    dialect = postgresql.dialect()
    chunks = [
        "-- Esquema operativo DepaFix Santiago Centro",
        "-- Generado desde operacion_terreno/db.py (SQLAlchemy)",
        "",
    ]
    for table in Base.metadata.sorted_tables:
        ddl = "\n".join(
            line.rstrip()
            for line in str(CreateTable(table).compile(dialect=dialect)).strip().splitlines()
        )
        chunks.append(f"{ddl};")
        for index in sorted(table.indexes, key=lambda item: item.name or ""):
            index_ddl = "\n".join(
                line.rstrip()
                for line in str(CreateIndex(index).compile(dialect=dialect)).strip().splitlines()
            )
            chunks.append(f"{index_ddl};")
        chunks.append("")
    path.write_text("\n".join(chunks) + "\n")
    return path
