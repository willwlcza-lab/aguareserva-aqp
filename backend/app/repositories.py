"""Consultas reutilizables. El servicio controla el commit y los bloqueos."""

from uuid import UUID
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from .models import Hogar, Recipiente, Movimiento, EventoAuditoria


class RepositorioAgua:
    def __init__(self, db: Session):
        self.db = db

    def obtener_hogar(self, owner_id: UUID, lock=False, required=True):
        query = select(Hogar).where(Hogar.owner_id == owner_id)
        if lock:
            query = query.with_for_update()
        result = self.db.scalar(query)
        if result is None and required:
            raise HTTPException(404, "Primero registra tu hogar.")
        return result

    def obtener_recipiente(self, household_id, container_id, lock=False):
        query = select(Recipiente).where(
            Recipiente.id == container_id, Recipiente.household_id == household_id
        )
        if lock:
            query = query.with_for_update()
        result = self.db.scalar(query)
        if result is None:
            raise HTTPException(404, "Recipiente no encontrado.")
        return result

    def listar_recipientes(self, household_id, active_only=True):
        query = select(Recipiente).where(Recipiente.household_id == household_id)
        if active_only:
            query = query.where(Recipiente.active.is_(True))
        return list(self.db.scalars(query.order_by(Recipiente.created_at)))

    def listar_movimientos(self, household_id, limit=100, offset=0):
        return list(
            self.db.execute(
                select(Movimiento, Recipiente.name, Recipiente.water_type)
                .join(Recipiente)
                .where(Recipiente.household_id == household_id)
                .order_by(Movimiento.created_at.desc(), Movimiento.id)
                .limit(limit)
                .offset(offset)
            )
        )


def registrar_auditoria(db, actor_id, action, entity_id=""):
    db.add(EventoAuditoria(actor_id=actor_id, action=action, entity_id=str(entity_id)))
