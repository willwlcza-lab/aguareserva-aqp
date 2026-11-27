"""Comandos locales: python -m app.cli crear-admin | cargar-demo (se admiten los nombres anteriores)."""

import argparse
from getpass import getpass
from decimal import Decimal
from sqlalchemy import select
from .core.db import SessionLocal
from .core.security import password_hasher
from .models import Usuario, Hogar
from .schemas import RegistroUsuario, DatosRecipiente, DatosMovimiento, DatosPlan
from .services.water import ServicioAgua, guardar_plan
from .repositories import registrar_auditoria
import uuid


def crear_administrador():
    data = RegistroUsuario(
        name=input("Nombre del administrador: "),
        email=input("Correo: ").strip(),
        password=getpass("Contraseña (mínimo 10 caracteres): "),
    )
    if data.password != getpass("Repite la contraseña: "):
        raise SystemExit("Las contraseñas no coinciden.")
    with SessionLocal.begin() as db:
        if db.scalar(select(Usuario).where(Usuario.email == str(data.email).lower())):
            raise SystemExit(
                "Ese correo ya existe. No se cambia su rol automáticamente."
            )
        user = Usuario(
            name=data.name,
            email=str(data.email).lower(),
            password_hash=password_hasher.hash(data.password),
            role="ADMIN",
        )
        db.add(user)
        db.flush()
        registrar_auditoria(db, user.id, "admin.created_cli", user.id)
    print("Administrador creado.")


def cargar_demostracion():
    """Un hogar ficticio, sin inflar estadísticas públicas. Repetible sin duplicar."""
    password = getpass(
        "Elige la contraseña de demo@example.com (mínimo 10 caracteres): "
    )
    if len(password) < 10 or len(password) > 128:
        raise SystemExit("La contraseña debe tener entre 10 y 128 caracteres.")
    with SessionLocal.begin() as db:
        if db.scalar(select(Usuario).where(Usuario.email == "demo@example.com")):
            raise SystemExit("La cuenta de demostración ya existe; no se sobrescribió.")
        user = Usuario(
            name="Familia Demo · datos ficticios",
            email="demo@example.com",
            password_hash=password_hasher.hash(password),
            role="USER",
        )
        db.add(user)
        db.flush()
        h = Hogar(
            owner_id=user.id,
            name="Hogar de demostración",
            district="Cerro Colorado",
            sector="Sector ficticio",
            members=4,
            drinking_daily=Decimal("12"),
            other_daily=Decimal("60"),
        )
        db.add(h)
        db.flush()
        service = ServicioAgua(db)
        service.crear_recipiente(
            user,
            DatosRecipiente(
                name="Bidón familiar",
                water_type="drinking",
                capacity=40,
                initial_balance=30,
            ),
        )
        c = service.crear_recipiente(
            user,
            DatosRecipiente(
                name="Tanque del hogar",
                water_type="other",
                capacity=200,
                initial_balance=120,
            ),
        )
        service.registrar_movimiento(
            user,
            uuid.UUID(c["id"]),
            DatosMovimiento(
                kind="consumption",
                liters=20,
                reason="Demostración académica",
                idempotency_key=uuid.uuid4(),
            ),
        )
        guardar_plan(
            db,
            user,
            DatosPlan(hours=72, reduction_percent=20, data_version=h.data_version),
        )
    print(
        "Demostración creada. Correo: demo@example.com. Todos sus datos son ficticios."
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command", choices=["crear-admin", "cargar-demo", "create-admin", "seed-demo"]
    )
    args = parser.parse_args()
    crear_administrador() if args.command in (
        "crear-admin",
        "create-admin",
    ) else cargar_demostracion()
