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
LIST_TYPE = MutableList.as_mutable(JSON_TYPE)


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
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    propiedad_id: Mapped[str] = mapped_column(String(32), index=True)
    direccion: Mapped[str] = mapped_column(String(255))
    departamento: Mapped[str | None] = mapped_column(String(32), nullable=True)
    torre: Mapped[str | None] = mapped_column(String(16), nullable=True)
    comuna: Mapped[str] = mapped_column(String(80), default="Santiago", server_default=text("'Santiago'"))
    bloque: Mapped[str | None] = mapped_column(String(32), nullable=True)
    segmento_ruta: Mapped[str | None] = mapped_column(String(16), nullable=True)
    parada_ruta: Mapped[int | None] = mapped_column(Integer, nullable=True)
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


def init_db(database_url: str):
    engine = create_engine(database_url, future=True)
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


def seed_pending_inspections(engine, df: pd.DataFrame) -> dict[str, int]:
    with Session(engine) as session:
        existing = set(session.scalars(select(InspeccionTerreno.propiedad_id)))
        inserted = 0
        skipped = 0
        for _, row in df.iterrows():
            propiedad_id = str(row["id"])
            if propiedad_id in existing:
                skipped += 1
                continue
            estado = "NO_APLICA" if bool(row["es_administracion"]) else "PENDIENTE"
            parada = row.get("parada_ruta")
            parada_int = int(parada) if pd.notna(parada) else None
            session.add(
                InspeccionTerreno(
                    propiedad_id=propiedad_id,
                    direccion=str(row["direccion_normalizada"]),
                    departamento=None if pd.isna(row["departamento"]) else str(row["departamento"]),
                    torre=None if pd.isna(row["torre"]) else str(row["torre"]),
                    comuna="Santiago",
                    bloque=None if pd.isna(row["bloque"]) else str(row["bloque"]),
                    segmento_ruta=None if pd.isna(row["segmento_ruta"]) else str(row["segmento_ruta"]),
                    parada_ruta=parada_int,
                    estado_visita=estado,
                    tipo_agua_caliente="SIN_INFORMACION",
                    observaciones=str(row["observaciones"]) if row["observaciones"] else None,
                    latitud=_to_float(row.get("lat")),
                    longitud=_to_float(row.get("lon")),
                )
            )
            inserted += 1
        session.commit()
    return {"insertadas": inserted, "omitidas": skipped}


def generate_postgres_ddl(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    dialect = postgresql.dialect()
    chunks = [
        "-- Esquema operativo DepaFix Santiago Centro",
        "-- Generado desde operacion_terreno/db.py (SQLAlchemy)",
        "",
    ]
    for table in Base.metadata.sorted_tables:
        ddl = str(CreateTable(table).compile(dialect=dialect)).strip()
        chunks.append(f"{ddl};")
        for index in sorted(table.indexes, key=lambda item: item.name or ""):
            chunks.append(f"{str(CreateIndex(index).compile(dialect=dialect)).strip()};")
        chunks.append("")
    path.write_text("\n".join(chunks) + "\n")
    return path
