from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from ..core.db import obtener_bd
from ..core.security import (
    validar_csrf,
    usuario_actual,
    sesion_opcional,
    emitir_sesion,
    verificar_contrasena,
    password_hasher,
    revocar_sesiones,
    limitar_intentos,
    DUMMY_HASH,
)
from ..core.config import settings
from ..models import Usuario
from ..schemas import RegistroUsuario, InicioSesion, PerfilUsuario, CambioContrasena
from ..repositories import registrar_auditoria

router = APIRouter(tags=["Cuentas"])


def vista_usuario(u):
    return {
        "id": str(u.id),
        "name": u.name,
        "email": u.email,
        "role": u.role,
        "active": u.active,
    }


@router.get("/auth/csrf")
def obtener_csrf(
    response: Response, session=Depends(sesion_opcional), db=Depends(obtener_bd)
):
    if session is None:
        session = emitir_sesion(db, response)
    return {"csrf_token": session.csrf_token}


@router.post(
    "/auth/registro", status_code=201, dependencies=[Depends(limitar_intentos)]
)
def registrarse(
    data: RegistroUsuario,
    response: Response,
    session=Depends(validar_csrf),
    db=Depends(obtener_bd),
):
    email = str(data.email).lower()
    if db.scalar(select(Usuario).where(Usuario.email == email)):
        raise HTTPException(
            409, "No se pudo crear la cuenta con ese correo. Intenta iniciar sesión."
        )
    user = Usuario(
        name=data.name,
        email=email,
        password_hash=password_hasher.hash(data.password),
        role="USER",
    )
    db.add(user)
    try:
        db.flush()
    except IntegrityError:
        raise HTTPException(409, "No se pudo crear la cuenta con ese correo.")
    session.revoked = True
    new = emitir_sesion(db, response, user.id)
    registrar_auditoria(db, user.id, "user.registered", user.id)
    return {"user": vista_usuario(user), "csrf_token": new.csrf_token}


@router.post("/auth/login", dependencies=[Depends(limitar_intentos)])
def iniciar_sesion(
    data: InicioSesion,
    response: Response,
    session=Depends(validar_csrf),
    db=Depends(obtener_bd),
):
    user = db.scalar(select(Usuario).where(Usuario.email == str(data.email).lower()))
    valid = verificar_contrasena(
        data.password, user.password_hash if user else DUMMY_HASH
    )
    if not user or not valid or not user.active:
        raise HTTPException(401, "Correo o contraseña incorrectos, o cuenta inactiva.")
    session.revoked = True
    new = emitir_sesion(db, response, user.id)
    registrar_auditoria(db, user.id, "user.login", user.id)
    return {"user": vista_usuario(user), "csrf_token": new.csrf_token}


@router.post("/auth/logout")
def cerrar_sesion(response: Response, session=Depends(validar_csrf)):
    session.revoked = True
    response.delete_cookie(
        settings.cookie_name,
        path="/",
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
    )
    return {"message": "Sesión cerrada."}


@router.get("/auth/me")
def mi_cuenta(user=Depends(usuario_actual)):
    return vista_usuario(user)


@router.patch("/perfil", dependencies=[Depends(validar_csrf)])
def editar_perfil(
    data: PerfilUsuario, user=Depends(usuario_actual), db=Depends(obtener_bd)
):
    user.name = data.name
    registrar_auditoria(db, user.id, "user.profile_updated", user.id)
    return vista_usuario(user)


@router.post("/perfil/cambiar-contrasena", dependencies=[Depends(validar_csrf)])
def cambiar_contrasena(
    data: CambioContrasena,
    response: Response,
    user=Depends(usuario_actual),
    db=Depends(obtener_bd),
):
    if not verificar_contrasena(data.current_password, user.password_hash):
        raise HTTPException(400, "La contraseña actual no es correcta.")
    user.password_hash = password_hasher.hash(data.new_password)
    revocar_sesiones(db, user.id)
    response.delete_cookie(settings.cookie_name, path="/")
    registrar_auditoria(db, user.id, "user.password_changed", user.id)
    return {"message": "Contraseña actualizada. Inicia sesión nuevamente."}
