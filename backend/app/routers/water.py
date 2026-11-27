from datetime import timezone
import csv
import io
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from ..core.db import obtener_bd
from ..core.security import usuario_actual, validar_csrf
from ..models import Hogar, Plan
from ..schemas import (
    DatosHogar,
    DatosRecipiente,
    EdicionRecipiente,
    DatosMovimiento,
    DatosSimulacion,
    DatosPlan,
)
from ..repositories import RepositorioAgua, registrar_auditoria
from ..services.water import (
    ServicioAgua,
    vista_hogar,
    vista_recipiente,
    vista_movimiento,
    calcular_plan,
    guardar_plan,
    vista_plan,
    resumen_hogar,
)

router = APIRouter(tags=["Hogar y agua"], dependencies=[Depends(usuario_actual)])


@router.get("/hogares/mio")
def mi_hogar(user=Depends(usuario_actual), db=Depends(obtener_bd)):
    h = RepositorioAgua(db).obtener_hogar(user.id, required=False)
    return vista_hogar(h) if h else None


@router.post("/hogares", status_code=201, dependencies=[Depends(validar_csrf)])
def crear_hogar(data: DatosHogar, user=Depends(usuario_actual), db=Depends(obtener_bd)):
    if RepositorioAgua(db).obtener_hogar(user.id, required=False):
        raise HTTPException(409, "Ya tienes un hogar registrado.")
    h = Hogar(owner_id=user.id, **data.model_dump())
    db.add(h)
    try:
        db.flush()
    except IntegrityError:
        raise HTTPException(409, "Ya tienes un hogar registrado.")
    registrar_auditoria(db, user.id, "household.created", h.id)
    return vista_hogar(h)


@router.patch("/hogares/mio", dependencies=[Depends(validar_csrf)])
def editar_hogar(
    data: DatosHogar, user=Depends(usuario_actual), db=Depends(obtener_bd)
):
    h = RepositorioAgua(db).obtener_hogar(user.id, lock=True)
    for key, value in data.model_dump().items():
        setattr(h, key, value)
    h.data_version += 1
    registrar_auditoria(db, user.id, "household.updated", h.id)
    return vista_hogar(h)


@router.get("/hogares/mio/panel")
def panel_hogar(user=Depends(usuario_actual), db=Depends(obtener_bd)):
    return resumen_hogar(db, user)


@router.get("/recipientes")
def listar_recipientes(user=Depends(usuario_actual), db=Depends(obtener_bd)):
    repo = RepositorioAgua(db)
    h = repo.obtener_hogar(user.id, required=False)
    return [vista_recipiente(c) for c in repo.listar_recipientes(h.id)] if h else []


@router.post("/recipientes", status_code=201, dependencies=[Depends(validar_csrf)])
def agregar_recipiente(
    data: DatosRecipiente, user=Depends(usuario_actual), db=Depends(obtener_bd)
):
    return ServicioAgua(db).crear_recipiente(user, data)


@router.patch("/recipientes/{container_id}", dependencies=[Depends(validar_csrf)])
def editar_recipiente(
    container_id: UUID,
    data: EdicionRecipiente,
    user=Depends(usuario_actual),
    db=Depends(obtener_bd),
):
    repo = RepositorioAgua(db)
    h = repo.obtener_hogar(user.id, lock=True)
    c = repo.obtener_recipiente(h.id, container_id, lock=True)
    if not c.active or data.capacity < c.balance:
        raise HTTPException(
            409, "Recipiente archivado o capacidad inferior al saldo actual."
        )
    c.name, c.capacity = data.name, data.capacity
    h.data_version += 1
    registrar_auditoria(db, user.id, "container.updated", c.id)
    return vista_recipiente(c)


@router.post(
    "/recipientes/{container_id}/archivar", dependencies=[Depends(validar_csrf)]
)
def archivar_recipiente(
    container_id: UUID, user=Depends(usuario_actual), db=Depends(obtener_bd)
):
    repo = RepositorioAgua(db)
    h = repo.obtener_hogar(user.id, lock=True)
    c = repo.obtener_recipiente(h.id, container_id, lock=True)
    if c.balance != 0:
        raise HTTPException(
            409,
            "Solo puedes archivar un recipiente vacío. Registra primero la salida o el ajuste.",
        )
    c.active = False
    h.data_version += 1
    registrar_auditoria(db, user.id, "container.archived", c.id)
    return {"message": "Recipiente archivado. Su historial se conserva."}


@router.post(
    "/recipientes/{container_id}/movimientos", dependencies=[Depends(validar_csrf)]
)
def agregar_movimiento(
    container_id: UUID,
    data: DatosMovimiento,
    user=Depends(usuario_actual),
    db=Depends(obtener_bd),
):
    return ServicioAgua(db).registrar_movimiento(user, container_id, data)


@router.get("/movimientos")
def listar_movimientos(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user=Depends(usuario_actual),
    db=Depends(obtener_bd),
):
    repo = RepositorioAgua(db)
    h = repo.obtener_hogar(user.id, required=False)
    return (
        [
            vista_movimiento(m, name, wt)
            for m, name, wt in repo.listar_movimientos(h.id, limit, offset)
        ]
        if h
        else []
    )


@router.post("/planes/simular", dependencies=[Depends(validar_csrf)])
def simular(
    data: DatosSimulacion, user=Depends(usuario_actual), db=Depends(obtener_bd)
):
    repo = RepositorioAgua(db)
    h = repo.obtener_hogar(user.id, lock=True)
    return calcular_plan(
        h, repo.listar_recipientes(h.id), data.hours, data.reduction_percent
    )


@router.post("/planes", status_code=201, dependencies=[Depends(validar_csrf)])
def crear_plan(data: DatosPlan, user=Depends(usuario_actual), db=Depends(obtener_bd)):
    return guardar_plan(db, user, data)


@router.get("/planes")
def listar_planes(user=Depends(usuario_actual), db=Depends(obtener_bd)):
    repo = RepositorioAgua(db)
    h = repo.obtener_hogar(user.id, required=False)
    if not h:
        return []
    rows = db.scalars(
        select(Plan)
        .where(Plan.household_id == h.id)
        .order_by(Plan.created_at.desc())
        .limit(50)
    )
    return [vista_plan(p, h.data_version) for p in rows]


@router.get("/reportes/movimientos.csv")
def exportar_movimientos(user=Depends(usuario_actual), db=Depends(obtener_bd)):
    repo = RepositorioAgua(db)
    h = repo.obtener_hogar(user.id)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "Fecha UTC",
            "Recipiente",
            "Uso declarado",
            "Tipo",
            "Litros",
            "Saldo posterior",
            "Motivo",
        ]
    )

    def safe(value):
        # Previene fórmulas al abrir contenido ingresado por usuarios en Excel.
        text = str(value)
        return (
            "'" + text
            if text.lstrip().startswith(("=", "+", "-", "@", "\t", "\r", "\n"))
            else text
        )

    offset = 0
    while rows := repo.listar_movimientos(h.id, 500, offset):
        for m, name, wt in rows:
            writer.writerow(
                [
                    m.created_at.astimezone(timezone.utc).isoformat(),
                    safe(name),
                    wt,
                    m.kind,
                    m.liters,
                    m.balance_after,
                    safe(m.reason),
                ]
            )
        offset += len(rows)
    return Response(
        "\ufeff" + output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="aguareserva_movimientos.csv"'
        },
    )
