"""Rutas de consulta y revisión. Todas las operaciones de escritura exigen CSRF."""

from datetime import timedelta
from typing import Literal
from uuid import UUID
from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException, Query
from pydantic import Field, model_validator
from sqlalchemy import select
from ..core.db import obtener_bd
from ..core.security import usuario_actual, usuario_administrador, validar_csrf
from ..models import (
    FuenteExterna,
    PublicacionExterna,
    EjecucionSincronizacion,
    AlertaHogar,
    Plan,
    ahora_utc,
)
from ..repositories import RepositorioAgua, registrar_auditoria
from ..services.fuentes import (
    sincronizar_fuentes,
    vista_publicacion,
    evaluar_reservas,
    generar_alertas,
    vigencia_publicacion,
)
from ..services.water import vista_plan
from ..fuentes.adaptadores import obtener_adaptadores
from ..schemas import Entrada

router = APIRouter(tags=["Fuentes y abastecimiento"])


@router.get("/fuentes")
def estado_fuentes(db=Depends(obtener_bd), usuario=Depends(usuario_actual)):
    resultado = []
    for adaptador in obtener_adaptadores():
        fuente = db.get(FuenteExterna, adaptador.clave)
        resultado.append(
            {
                "clave": adaptador.clave,
                "nombre": adaptador.nombre,
                "tipo": adaptador.tipo,
                "url": adaptador.url,
                "ultimo_intento": fuente.ultimo_intento if fuente else None,
                "ultimo_exito": fuente.ultimo_exito if fuente else None,
                "intervalo_minutos": fuente.intervalo_minutos
                if fuente
                else adaptador.intervalo,
                "estado": "sin_consultar"
                if not fuente or not fuente.ultimo_intento
                else "error_o_parcial"
                if fuente.error
                else "desactualizada"
                if not fuente.ultimo_exito
                or fuente.ultimo_exito
                < ahora_utc() - timedelta(minutes=fuente.intervalo_minutos * 2)
                else "consultada",
                "detalle": fuente.error if fuente and usuario.role == "ADMIN" else None,
            }
        )
    return resultado


@router.get("/publicaciones")
def listar_publicaciones(
    categoria: Literal["corte", "punto", "orientacion"] = "corte",
    distrito: str = "",
    solo_mi_hogar: bool = False,
    historicos: bool = False,
    limite: int = Query(100, ge=1, le=200),
    desplazamiento: int = Query(0, ge=0),
    db=Depends(obtener_bd),
    usuario=Depends(usuario_actual),
):
    hogar = RepositorioAgua(db).obtener_hogar(usuario.id, required=False)
    consulta = (
        select(PublicacionExterna, FuenteExterna)
        .join(FuenteExterna)
        .where(
            PublicacionExterna.categoria == categoria,
            PublicacionExterna.revision != "descartado",
        )
    )
    filtro = hogar.district if solo_mi_hogar and hogar else distrito
    if solo_mi_hogar and not hogar:
        return {
            "registros": [],
            "hay_mas": False,
            "mensaje": "Registra tu hogar para filtrar sus avisos.",
        }
    if filtro:
        consulta = consulta.where(
            PublicacionExterna.datos["distritos"].contains([filtro])
        )
    # Se ordena por fecha del hecho, no por el orden del importador.
    campo = (
        "inicio"
        if categoria == "corte"
        else "fecha_atencion"
        if categoria == "punto"
        else "publicado"
    )
    filas = db.execute(
        consulta.order_by(
            PublicacionExterna.datos[campo].astext.desc().nullslast(),
            PublicacionExterna.id,
        )
    ).all()
    registros = []
    for p, f in filas:
        if not historicos and vigencia_publicacion(p) in (
            "historico",
            "plazo_estimado_pasado",
        ):
            continue
        registros.append(vista_publicacion(p, f, hogar))
    return {
        "registros": registros[desplazamiento : desplazamiento + limite],
        "hay_mas": len(registros) > desplazamiento + limite,
        "total": len(registros),
    }


class EscenarioAviso(Entrada):
    horas_manuales: int | None = Field(default=None, ge=1, le=720)


class PlanAviso(EscenarioAviso):
    version_datos: int


@router.post(
    "/publicaciones/{identificador}/evaluar", dependencies=[Depends(validar_csrf)]
)
def evaluar_aviso(
    identificador: UUID,
    datos: EscenarioAviso,
    db=Depends(obtener_bd),
    usuario=Depends(usuario_actual),
):
    aviso = db.get(PublicacionExterna, identificador)
    if not aviso or aviso.categoria != "corte" or aviso.revision == "descartado":
        raise HTTPException(404, "Aviso no encontrado")
    return evaluar_reservas(db, usuario, aviso, datos.horas_manuales)


@router.post(
    "/publicaciones/{identificador}/guardar-plan", dependencies=[Depends(validar_csrf)]
)
def guardar_plan_aviso(
    identificador: UUID,
    datos: PlanAviso,
    db=Depends(obtener_bd),
    usuario=Depends(usuario_actual),
):
    hogar = RepositorioAgua(db).obtener_hogar(usuario.id, lock=True)
    if hogar.data_version != datos.version_datos:
        raise HTTPException(409, "Tus datos cambiaron; vuelve a evaluar el aviso.")
    aviso = db.get(PublicacionExterna, identificador)
    if not aviso or aviso.categoria != "corte" or aviso.revision == "descartado":
        raise HTTPException(404, "Aviso no encontrado")
    evaluacion = evaluar_reservas(db, usuario, aviso, datos.horas_manuales)
    instantanea = dict(evaluacion["proyeccion_inicio"] or evaluacion["actual"])
    instantanea["aviso"] = {
        "id": str(aviso.id),
        "titulo": aviso.datos["titulo"],
        "url": aviso.datos["url"],
        "inicio": aviso.datos.get("inicio"),
        "fin_estimado": aviso.datos.get("fin_estimado"),
        "revision": aviso.revision,
        "evaluado": ahora_utc().isoformat(),
    }
    plan = Plan(
        household_id=hogar.id,
        hours=evaluacion["horas"],
        data_version=hogar.data_version,
        snapshot=instantanea,
    )
    db.add(plan)
    db.flush()
    registrar_auditoria(db, usuario.id, "plan.aviso_guardado", plan.id)
    return vista_plan(plan, hogar.data_version)


@router.get("/alertas")
def mis_alertas(db=Depends(obtener_bd), usuario=Depends(usuario_actual)):
    hogar = RepositorioAgua(db).obtener_hogar(usuario.id, required=False)
    if not hogar:
        return []
    filas = db.execute(
        select(AlertaHogar, PublicacionExterna)
        .join(PublicacionExterna)
        .where(
            AlertaHogar.hogar_id == hogar.id,
            PublicacionExterna.revision.in_(["aprobado", "automatico"]),
        )
        .order_by(AlertaHogar.creada.desc())
        .limit(30)
    )
    return [
        {
            "id": str(a.id),
            "publicacion_id": str(p.id),
            "titulo": p.datos["titulo"],
            "leida": a.leida,
            "creada": a.creada,
            "vigencia": vigencia_publicacion(p),
        }
        for a, p in filas
        if hogar.district in p.datos.get("distritos", [])
    ]


@router.post("/alertas/{identificador}/leer", dependencies=[Depends(validar_csrf)])
def leer_alerta(
    identificador: UUID, db=Depends(obtener_bd), usuario=Depends(usuario_actual)
):
    hogar = RepositorioAgua(db).obtener_hogar(usuario.id)
    alerta = db.get(AlertaHogar, identificador)
    if not alerta or alerta.hogar_id != hogar.id:
        raise HTTPException(404, "Alerta no encontrada")
    alerta.leida = True
    return {"mensaje": "Alerta marcada como leída"}


@router.post(
    "/admin/fuentes/sincronizar", status_code=202, dependencies=[Depends(validar_csrf)]
)
def sincronizar_ahora(tareas: BackgroundTasks, usuario=Depends(usuario_administrador)):
    tareas.add_task(sincronizar_fuentes, forzar=True)
    return {
        "mensaje": "Consulta solicitada. Revisa el estado en unos momentos. Si ya hay una en curso se conserva esa ejecución; mínimo un minuto entre consultas."
    }


@router.get("/admin/fuentes/historial")
def historial_sincronizacion(
    db=Depends(obtener_bd), usuario=Depends(usuario_administrador)
):
    return list(
        db.scalars(
            select(EjecucionSincronizacion)
            .order_by(EjecucionSincronizacion.id.desc())
            .limit(60)
        )
    )


@router.get("/admin/fuentes/revision")
def pendientes_revision(
    limite: int = Query(50, ge=1, le=200),
    desplazamiento: int = Query(0, ge=0),
    db=Depends(obtener_bd),
    usuario=Depends(usuario_administrador),
):
    filas = db.execute(
        select(PublicacionExterna, FuenteExterna)
        .join(FuenteExterna)
        .where(PublicacionExterna.revision == "pendiente")
        .order_by(
            PublicacionExterna.datos["inicio"].astext.desc().nullslast(),
            PublicacionExterna.id,
        )
        .offset(desplazamiento)
        .limit(limite + 1)
    ).all()
    return {
        "registros": [vista_publicacion(p, f) for p, f in filas[:limite]],
        "hay_mas": len(filas) > limite,
    }


class RevisionPublicacion(Entrada):
    estado: Literal["aprobado", "descartado"]
    nota: str = Field(min_length=10, max_length=1000)
    latitud: float | None = Field(default=None, ge=-90, le=90)
    longitud: float | None = Field(default=None, ge=-180, le=180)
    referencia_coordenadas: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def revisar_coordenadas(self):
        if (self.latitud is None) != (self.longitud is None):
            raise ValueError("Completa latitud y longitud")
        if self.latitud is not None and (
            not self.referencia_coordenadas
            or not self.referencia_coordenadas.startswith("https://")
        ):
            raise ValueError(
                "Incluye un enlace HTTPS que sustente la ubicación verificada"
            )
        return self


@router.patch(
    "/admin/fuentes/publicaciones/{identificador}", dependencies=[Depends(validar_csrf)]
)
def revisar_publicacion(
    identificador: UUID,
    datos: RevisionPublicacion,
    db=Depends(obtener_bd),
    usuario=Depends(usuario_administrador),
):
    p = db.scalar(
        select(PublicacionExterna)
        .where(PublicacionExterna.id == identificador)
        .with_for_update()
    )
    if not p:
        raise HTTPException(404, "Publicación no encontrada")
    if datos.latitud is not None:
        if p.categoria != "punto":
            raise HTTPException(
                422, "Las coordenadas corresponden a puntos de abastecimiento"
            )
        p.datos = {
            **p.datos,
            "latitud": datos.latitud,
            "longitud": datos.longitud,
            "procedencia_coordenadas": datos.referencia_coordenadas,
            "coordenadas_verificadas": True,
        }
    p.revision = datos.estado
    p.observacion = datos.nota
    p.actualizado = ahora_utc()
    registrar_auditoria(db, usuario.id, "fuente.revisada_" + datos.estado, p.id)
    db.flush()
    generar_alertas(db)
    return {
        "mensaje": "Revisión registrada. Una aprobación local no cambia el carácter de la fuente ni confirma atención en tiempo real."
    }
