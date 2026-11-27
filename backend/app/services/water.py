from datetime import timezone
import hashlib
import json
import uuid
from decimal import Decimal, ROUND_CEILING
from datetime import timedelta
from fastapi import HTTPException
from sqlalchemy import select
from ..models import Recipiente, Movimiento, Plan, ahora_utc
from ..repositories import RepositorioAgua, registrar_auditoria

LABELS = {"drinking": "Consumo humano (declarado)", "other": "Otros usos"}


def numero(value):
    return float(value) if value is not None else None


def vista_recipiente(c):
    return {
        "id": str(c.id),
        "name": c.name,
        "water_type": c.water_type,
        "capacity": numero(c.capacity),
        "balance": numero(c.balance),
        "active": c.active,
    }


def vista_hogar(h):
    return {
        "id": str(h.id),
        "name": h.name,
        "district": h.district,
        "sector": h.sector,
        "members": h.members,
        "drinking_daily": numero(h.drinking_daily),
        "other_daily": numero(h.other_daily),
        "data_version": h.data_version,
    }


def vista_movimiento(m, name=None, water_type=None):
    return {
        "id": str(m.id),
        "container_id": str(m.container_id),
        "container_name": name,
        "water_type": water_type,
        "kind": m.kind,
        "liters": numero(m.liters),
        "balance_after": numero(m.balance_after),
        "reason": m.reason,
        "created_at": m.created_at.astimezone(timezone.utc).isoformat(),
    }


class ServicioAgua:
    def __init__(self, db):
        self.db = db
        self.repo = RepositorioAgua(db)

    def crear_recipiente(self, user, data):
        h = self.repo.obtener_hogar(user.id, lock=True)
        c = Recipiente(
            household_id=h.id,
            name=data.name,
            water_type=data.water_type,
            capacity=data.capacity,
            balance=data.initial_balance,
        )
        self.db.add(c)
        self.db.flush()
        if data.initial_balance > 0:
            self.db.add(
                Movimiento(
                    container_id=c.id,
                    actor_id=user.id,
                    kind="initial",
                    liters=data.initial_balance,
                    balance_after=data.initial_balance,
                    reason="Reserva declarada al registrar el recipiente",
                    idempotency_key=str(uuid.uuid4()),
                    fingerprint="initial",
                )
            )
        h.data_version += 1
        registrar_auditoria(self.db, user.id, "container.created", c.id)
        return vista_recipiente(c)

    def registrar_movimiento(self, user, container_id, data):
        # Orden de bloqueo único: hogar -> recipiente. La comprobación y el saldo
        # se confirman en la misma transacción para evitar consumos simultáneos.
        h = self.repo.obtener_hogar(user.id, lock=True)
        c = self.repo.obtener_recipiente(h.id, container_id, lock=True)
        canonical = {
            "container": str(c.id),
            "kind": data.kind,
            "liters": format(data.liters.quantize(Decimal(".01")), "f"),
            "reason": data.reason,
        }
        fingerprint = hashlib.sha256(
            json.dumps(canonical, sort_keys=True).encode()
        ).hexdigest()
        previous = self.db.scalar(
            select(Movimiento).where(
                Movimiento.actor_id == user.id,
                Movimiento.idempotency_key == str(data.idempotency_key),
            )
        )
        if previous:
            if previous.fingerprint != fingerprint:
                raise HTTPException(
                    409, "La clave de operación ya fue utilizada con datos diferentes."
                )
            return vista_movimiento(previous, c.name, c.water_type)
        if not c.active:
            raise HTTPException(409, "El recipiente está archivado.")
        sign = -1 if data.kind in ("consumption", "adjust_down") else 1
        new_balance = c.balance + sign * data.liters
        if new_balance < 0:
            raise HTTPException(409, "El consumo supera el agua disponible.")
        if new_balance > c.capacity:
            raise HTTPException(409, "La entrada supera la capacidad del recipiente.")
        c.balance = new_balance
        h.data_version += 1
        movement = Movimiento(
            container_id=c.id,
            actor_id=user.id,
            kind=data.kind,
            liters=data.liters,
            balance_after=new_balance,
            reason=data.reason,
            idempotency_key=str(data.idempotency_key),
            fingerprint=fingerprint,
        )
        self.db.add(movement)
        self.db.flush()
        registrar_auditoria(self.db, user.id, "movement.created", movement.id)
        return vista_movimiento(movement, c.name, c.water_type)


def calcular_plan(h, containers, hours, reduction_percent=0):
    """Función pura: unidades en litros, horizonte en horas, sin modelo predictivo.

    La reducción hipotética solo afecta otros usos. Nunca supone que agua de
    otros usos sea apta para beber. Redondeo del requerimiento hacia arriba.
    """
    items = []
    actions = []
    for kind, daily in (("drinking", h.drinking_daily), ("other", h.other_daily)):
        available = sum(
            (c.balance for c in containers if c.water_type == kind), Decimal(0)
        )
        capacity = sum(
            (c.capacity for c in containers if c.water_type == kind), Decimal(0)
        )
        effective = daily
        if kind == "other" and daily is not None:
            effective = daily * (Decimal(100) - Decimal(reduction_percent)) / 100
        required = (
            (effective * Decimal(hours) / 24).quantize(
                Decimal(".01"), rounding=ROUND_CEILING
            )
            if effective is not None
            else None
        )
        deficit = (
            max(Decimal(0), required - available) if required is not None else None
        )
        fill = min(deficit, capacity - available) if deficit is not None else None
        days = (
            (available / effective).quantize(Decimal(".01"))
            if effective is not None and effective > 0
            else None
        )
        if daily is None:
            state = "unknown"
            actions.append(
                f"Completa la estimación diaria de {LABELS[kind].lower()} para evaluar este uso."
            )
        elif daily == 0:
            state = "no_demand"
            actions.append(
                f"Revisa la estimación de {LABELS[kind].lower()}: has declarado 0 litros diarios."
            )
        elif deficit > 0:
            state = "deficit"
            if fill > 0:
                actions.append(
                    f"Planifica reponer {fill:.2f} L para {LABELS[kind].lower()} antes del corte, si hay abastecimiento disponible."
                )
            if deficit > fill:
                actions.append(
                    f"Faltan {deficit - fill:.2f} L adicionales de capacidad para {LABELS[kind].lower()}; evalúa almacenamiento adecuado o abastecimiento alternativo verificado."
                )
        else:
            state = "covered"
        items.append(
            {
                "water_type": kind,
                "label": LABELS[kind],
                "daily": numero(daily),
                "effective_daily": numero(effective),
                "available": numero(available),
                "capacity": numero(capacity),
                "required": numero(required),
                "deficit": numero(deficit),
                "fillable": numero(fill),
                "extra_capacity": numero(deficit - fill)
                if deficit is not None
                else None,
                "days": numero(days),
                "state": state,
            }
        )
    states = [i["state"] for i in items]
    status = (
        "incomplete"
        if "unknown" in states or "no_demand" in states
        else "deficit"
        if "deficit" in states
        else "covered"
    )
    if not actions:
        actions.append(
            "La reserva declarada cubre este escenario. Registra consumos y vuelve a simular si cambia la duración del corte."
        )
    return {
        "hours": hours,
        "reduction_percent": reduction_percent,
        "data_version": h.data_version,
        "status": status,
        "items": items,
        "actions": actions,
        "basis": "Estimación declarada por el hogar; escenario manual, sin predicción ni aviso oficial asociado.",
    }


def guardar_plan(db, user, data):
    repo = RepositorioAgua(db)
    h = repo.obtener_hogar(user.id, lock=True)
    if h.data_version != data.data_version:
        raise HTTPException(
            409,
            "Tus reservas o estimaciones cambiaron. Vuelve a simular antes de guardar.",
        )
    snapshot = calcular_plan(
        h, repo.listar_recipientes(h.id), data.hours, data.reduction_percent
    )
    p = Plan(
        household_id=h.id,
        hours=data.hours,
        data_version=h.data_version,
        snapshot=snapshot,
    )
    db.add(p)
    db.flush()
    registrar_auditoria(db, user.id, "plan.saved", p.id)
    return vista_plan(p, h.data_version)


def vista_plan(p, current_version):
    return {
        "id": str(p.id),
        "created_at": p.created_at.astimezone(timezone.utc).isoformat(),
        "outdated": p.data_version != current_version,
        "snapshot": p.snapshot,
    }


def resumen_hogar(db, user):
    repo = RepositorioAgua(db)
    h = repo.obtener_hogar(user.id, required=False)
    if not h:
        return {"household": None}
    containers = repo.listar_recipientes(h.id)
    preview = calcular_plan(h, containers, 24)
    today = (
        ahora_utc().astimezone(__import__("zoneinfo").ZoneInfo("America/Lima")).date()
    )
    start = today - timedelta(days=6)
    rows = db.scalars(
        select(Movimiento)
        .join(Recipiente)
        .where(
            Recipiente.household_id == h.id,
            Movimiento.kind == "consumption",
            Movimiento.created_at >= ahora_utc() - timedelta(days=8),
        )
    )
    sums = {}
    for m in rows:
        day = m.created_at.astimezone(
            __import__("zoneinfo").ZoneInfo("America/Lima")
        ).date()
        sums[day] = sums.get(day, Decimal(0)) + m.liters
    chart = [
        {
            "date": (start + timedelta(days=i)).isoformat(),
            "liters": numero(sums.get(start + timedelta(days=i))),
        }
        for i in range(7)
    ]
    recent = [
        vista_movimiento(m, name, wt)
        for m, name, wt in repo.listar_movimientos(h.id, limit=5)
    ]
    total = sum((c.balance for c in containers), Decimal(0))
    capacity = sum((c.capacity for c in containers), Decimal(0))
    return {
        "household": vista_hogar(h),
        "containers": [vista_recipiente(c) for c in containers],
        "total": numero(total),
        "capacity": numero(capacity),
        "plan24": preview,
        "chart": chart,
        "recent": recent,
    }
