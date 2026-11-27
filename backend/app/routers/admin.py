from datetime import timezone
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from ..core.db import obtener_bd
from ..core.security import usuario_administrador, validar_csrf, revocar_sesiones
from ..models import Usuario, Hogar, Recipiente, Plan, EventoAuditoria
from ..schemas import EstadoUsuario
from ..repositories import registrar_auditoria
from .auth import vista_usuario

router = APIRouter(
    prefix="/admin",
    tags=["Administración"],
    dependencies=[Depends(usuario_administrador)],
)


@router.get("/resumen")
def resumen_administrativo(db=Depends(obtener_bd)):
    return {
        "users": db.scalar(select(func.count()).select_from(Usuario)),
        "households": db.scalar(select(func.count()).select_from(Hogar)),
        "containers": db.scalar(
            select(func.count())
            .select_from(Recipiente)
            .where(Recipiente.active.is_(True))
        ),
        "plans": db.scalar(select(func.count()).select_from(Plan)),
        "districts": [
            {"district": district, "households": count}
            for district, count in db.execute(
                select(Hogar.district, func.count()).group_by(Hogar.district)
            )
        ],
    }


@router.get("/usuarios")
def listar_usuarios(offset: int = Query(0, ge=0), db=Depends(obtener_bd)):
    return [
        vista_usuario(u)
        for u in db.scalars(
            select(Usuario)
            .order_by(Usuario.created_at.desc())
            .offset(offset)
            .limit(100)
        )
    ]


@router.patch("/usuarios/{user_id}/estado", dependencies=[Depends(validar_csrf)])
def cambiar_estado_usuario(
    user_id: UUID,
    data: EstadoUsuario,
    actor=Depends(usuario_administrador),
    db=Depends(obtener_bd),
):
    # Serializa los cambios de administradores para preservar al menos uno activo.
    admins = list(
        db.scalars(
            select(Usuario)
            .where(Usuario.role == "ADMIN")
            .order_by(Usuario.id)
            .with_for_update()
        )
    )
    user = db.scalar(select(Usuario).where(Usuario.id == user_id).with_for_update())
    if not user:
        raise HTTPException(404, "Usuario no encontrado.")
    if not data.active and user.id == actor.id:
        raise HTTPException(
            409, "No puedes desactivar tu propia cuenta de administrador."
        )
    if not data.active and user.role == "ADMIN" and sum(a.active for a in admins) <= 1:
        raise HTTPException(409, "Debe permanecer al menos un administrador activo.")
    user.active = data.active
    if not data.active:
        revocar_sesiones(db, user.id)
    registrar_auditoria(
        db, actor.id, "user.enabled" if data.active else "user.disabled", user.id
    )
    return vista_usuario(user)


@router.get("/auditoria")
def listar_auditoria(offset: int = Query(0, ge=0), db=Depends(obtener_bd)):
    rows = db.execute(
        select(EventoAuditoria, Usuario.name)
        .outerjoin(Usuario, Usuario.id == EventoAuditoria.actor_id)
        .order_by(EventoAuditoria.created_at.desc(), EventoAuditoria.id.desc())
        .offset(offset)
        .limit(100)
    )
    return [
        {
            "id": e.id,
            "action": e.action,
            "actor": name or "Sistema",
            "entity_id": e.entity_id,
            "created_at": e.created_at.astimezone(timezone.utc).isoformat(),
        }
        for e, name in rows
    ]
