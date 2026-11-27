from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID
from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
    model_validator,
)
from .catalogs import AREQUIPA_DISTRICTS

Liters = Annotated[Decimal, Field(ge=0, le=99999999, max_digits=12, decimal_places=2)]
PositiveLiters = Annotated[
    Decimal, Field(gt=0, le=99999999, max_digits=12, decimal_places=2)
]
WaterType = Literal["drinking", "other"]


class Entrada(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class RegistroUsuario(Entrada):
    name: str = Field(min_length=2, max_length=80)
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)
    # No strip en contraseña: los espacios forman parte de la credencial.
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)

    @field_validator("name")
    @classmethod
    def validar_nombre(cls, v):
        v = v.strip()
        if len(v) < 2:
            raise ValueError("Escribe tu nombre.")
        return v


class InicioSesion(Entrada):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)


class PerfilUsuario(Entrada):
    name: str = Field(min_length=2, max_length=80)


class CambioContrasena(Entrada):
    current_password: str
    new_password: str = Field(min_length=10, max_length=128)
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)


class DatosHogar(Entrada):
    name: str = Field(min_length=2, max_length=80)
    district: str = Field(min_length=2, max_length=80)
    sector: str = Field(default="", max_length=120)
    members: int = Field(ge=1, le=100)
    drinking_daily: Liters | None = None
    other_daily: Liters | None = None

    @field_validator("district")
    @classmethod
    def validar_distrito(cls, value):
        if value not in AREQUIPA_DISTRICTS:
            raise ValueError(
                "Selecciona un distrito de la provincia de Arequipa de la lista."
            )
        return value


class DatosRecipiente(Entrada):
    name: str = Field(min_length=2, max_length=80)
    water_type: WaterType
    capacity: PositiveLiters
    initial_balance: Liters = Decimal("0")

    @model_validator(mode="after")
    def validar_saldo(self):
        if self.initial_balance > self.capacity:
            raise ValueError("La reserva inicial no puede superar la capacidad.")
        return self


class EdicionRecipiente(Entrada):
    name: str = Field(min_length=2, max_length=80)
    capacity: PositiveLiters


class DatosMovimiento(Entrada):
    kind: Literal["refill", "consumption", "adjust_up", "adjust_down"]
    liters: PositiveLiters
    reason: str = Field(default="", max_length=240)
    idempotency_key: UUID

    @model_validator(mode="after")
    def exigir_motivo(self):
        if self.kind.startswith("adjust") and len(self.reason) < 5:
            raise ValueError("Explica el motivo del ajuste (mínimo 5 caracteres).")
        return self


class DatosSimulacion(Entrada):
    hours: int = Field(ge=1, le=720)
    reduction_percent: int = Field(default=0, ge=0, le=50)


class DatosPlan(DatosSimulacion):
    data_version: int = Field(ge=1)


class EstadoUsuario(Entrada):
    active: bool
