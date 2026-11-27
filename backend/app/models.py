"""Persistencia relacional. Las reglas de negocio viven en los servicios."""

from datetime import datetime, timezone
from decimal import Decimal
import uuid
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from .core.db import Base


def ahora_utc():
    return datetime.now(timezone.utc)


class Usuario(Base):
    __tablename__ = "usuarios"
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(80))
    email: Mapped[str] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(String(10), default="USER")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=ahora_utc
    )
    __table_args__ = (CheckConstraint("role IN ('USER','ADMIN')"),)


class SesionAcceso(Base):
    __tablename__ = "sesiones"
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("usuarios.id"), nullable=True, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    csrf_token: Mapped[str] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=ahora_utc
    )
    last_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=ahora_utc
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)


class LimiteIntentos(Base):
    __tablename__ = "limites_intentos"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    count: Mapped[int] = mapped_column(Integer, default=1)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Hogar(Base):
    __tablename__ = "hogares"
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuarios.id"), unique=True)
    name: Mapped[str] = mapped_column(String(80))
    district: Mapped[str] = mapped_column(String(80))
    sector: Mapped[str] = mapped_column(String(120), default="")
    members: Mapped[int] = mapped_column(Integer)
    drinking_daily: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2), nullable=True
    )
    other_daily: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    data_version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=ahora_utc
    )
    __table_args__ = (
        CheckConstraint("members > 0"),
        CheckConstraint("drinking_daily IS NULL OR drinking_daily >= 0"),
        CheckConstraint("other_daily IS NULL OR other_daily >= 0"),
    )


class Recipiente(Base):
    __tablename__ = "recipientes"
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    household_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("hogares.id"), index=True
    )
    name: Mapped[str] = mapped_column(String(80))
    water_type: Mapped[str] = mapped_column(String(20))
    capacity: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    balance: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=ahora_utc
    )
    __table_args__ = (
        CheckConstraint("capacity > 0 AND balance >= 0 AND balance <= capacity"),
        CheckConstraint("water_type IN ('drinking','other')"),
    )


class Movimiento(Base):
    __tablename__ = "movimientos"
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    container_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("recipientes.id"), index=True
    )
    actor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuarios.id"))
    kind: Mapped[str] = mapped_column(String(20))
    liters: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    balance_after: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    reason: Mapped[str] = mapped_column(String(240), default="")
    idempotency_key: Mapped[str] = mapped_column(String(80))
    fingerprint: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=ahora_utc
    )
    __table_args__ = (
        UniqueConstraint("actor_id", "idempotency_key", name="uq_movement_actor_key"),
        CheckConstraint("liters > 0"),
        CheckConstraint(
            "kind IN ('initial','refill','consumption','adjust_up','adjust_down')"
        ),
    )


class Plan(Base):
    __tablename__ = "planes"
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    household_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("hogares.id"), index=True
    )
    hours: Mapped[int] = mapped_column(Integer)
    data_version: Mapped[int] = mapped_column(Integer)
    snapshot: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=ahora_utc
    )
    __table_args__ = (CheckConstraint("hours > 0 AND hours <= 720"),)


class EventoAuditoria(Base):
    __tablename__ = "eventos_auditoria"
    id: Mapped[int] = mapped_column(primary_key=True)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("usuarios.id"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(80))
    entity_id: Mapped[str] = mapped_column(String(80), default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=ahora_utc
    )


class FuenteExterna(Base):
    """Estado observable de cada conector; un fallo no borra el último éxito."""

    __tablename__ = "fuentes_externas"
    clave: Mapped[str] = mapped_column(String(80), primary_key=True)
    nombre: Mapped[str] = mapped_column(String(120))
    tipo: Mapped[str] = mapped_column(String(20))
    url: Mapped[str] = mapped_column(Text)
    intervalo_minutos: Mapped[int] = mapped_column(Integer)
    ultimo_intento: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ultimo_exito: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str] = mapped_column(Text, default="")


class PublicacionExterna(Base):
    """Documento normalizado: corte, punto o recurso de orientación.

    JSONB conserva campos que varían entre fuentes; identidad, origen y revisión
    tienen columnas propias y restricciones. No contiene datos privados del hogar.
    """

    __tablename__ = "publicaciones_externas"
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    fuente_clave: Mapped[str] = mapped_column(
        ForeignKey("fuentes_externas.clave"), index=True
    )
    clave_origen: Mapped[str] = mapped_column(String(64))
    categoria: Mapped[str] = mapped_column(String(20), index=True)
    datos: Mapped[dict] = mapped_column(JSONB)
    hash_contenido: Mapped[str] = mapped_column(String(64))
    revision: Mapped[str] = mapped_column(String(20), default="pendiente")
    observacion: Mapped[str] = mapped_column(Text, default="")
    consultado: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=ahora_utc
    )
    actualizado: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=ahora_utc
    )
    __table_args__ = (
        UniqueConstraint("fuente_clave", "clave_origen", name="uq_publicacion_origen"),
        CheckConstraint("categoria IN ('corte','punto','orientacion')"),
        CheckConstraint(
            "revision IN ('automatico','pendiente','aprobado','descartado')"
        ),
    )


class EjecucionSincronizacion(Base):
    __tablename__ = "ejecuciones_sincronizacion"
    id: Mapped[int] = mapped_column(primary_key=True)
    fuente_clave: Mapped[str] = mapped_column(ForeignKey("fuentes_externas.clave"))
    iniciado: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=ahora_utc
    )
    finalizado: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    estado: Mapped[str] = mapped_column(String(20), default="en_progreso")
    nuevos: Mapped[int] = mapped_column(Integer, default=0)
    actualizados: Mapped[int] = mapped_column(Integer, default=0)
    detalle: Mapped[str] = mapped_column(Text, default="")


class AlertaHogar(Base):
    __tablename__ = "alertas_hogar"
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    hogar_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hogares.id"), index=True)
    publicacion_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("publicaciones_externas.id")
    )
    creada: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora_utc)
    leida: Mapped[bool] = mapped_column(Boolean, default=False)
    __table_args__ = (
        UniqueConstraint("hogar_id", "publicacion_id", name="uq_alerta_hogar_aviso"),
    )
