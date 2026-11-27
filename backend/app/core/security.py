import hashlib
import secrets
from datetime import timedelta
from fastapi import Depends, HTTPException, Request, Response
from pwdlib import PasswordHash
from sqlalchemy import select, update, delete
from sqlalchemy.dialects.postgresql import insert
from .config import settings
from .db import obtener_bd, SessionLocal
from ..models import SesionAcceso, Usuario, LimiteIntentos, ahora_utc

password_hasher = PasswordHash.recommended()
DUMMY_HASH = password_hasher.hash(secrets.token_urlsafe(24))


def resumir_token(value):
    return hashlib.sha256(value.encode()).hexdigest()


def verificar_contrasena(password, encoded):
    return password_hasher.verify(password, encoded)


def emitir_sesion(db, response: Response, user_id=None):
    token = secrets.token_urlsafe(48)
    session = SesionAcceso(
        user_id=user_id,
        token_hash=resumir_token(token),
        csrf_token=secrets.token_urlsafe(32),
        expires_at=ahora_utc() + timedelta(hours=settings.session_hours),
    )
    db.add(session)
    db.flush()
    response.set_cookie(
        settings.cookie_name,
        token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=settings.session_hours * 3600,
        path="/",
    )
    return session


def sesion_opcional(request: Request, db=Depends(obtener_bd)):
    token = request.cookies.get(settings.cookie_name)
    if not token:
        return None
    session = db.scalar(
        select(SesionAcceso).where(
            SesionAcceso.token_hash == resumir_token(token),
            SesionAcceso.revoked.is_(False),
        )
    )
    now = ahora_utc()
    if (
        not session
        or session.expires_at <= now
        or session.last_seen + timedelta(minutes=settings.session_idle_minutes) <= now
    ):
        return None
    session.last_seen = now
    return session


def validar_csrf(request: Request, session=Depends(sesion_opcional)):
    supplied = request.headers.get("X-CSRF-Token", "")
    if (
        not session
        or not supplied
        or not secrets.compare_digest(supplied, session.csrf_token)
    ):
        raise HTTPException(
            403,
            "La sesión de seguridad venció. Actualiza la página e inténtalo otra vez.",
        )
    return session


def usuario_actual(session=Depends(sesion_opcional), db=Depends(obtener_bd)):
    user = db.get(Usuario, session.user_id) if session and session.user_id else None
    if user is None or not user.active:
        raise HTTPException(401, "Inicia sesión para continuar.")
    return user


def usuario_administrador(user=Depends(usuario_actual)):
    if user.role != "ADMIN":
        raise HTTPException(403, "Esta sección requiere una cuenta de administrador.")
    return user


def revocar_sesiones(db, user_id):
    db.execute(
        update(SesionAcceso).where(SesionAcceso.user_id == user_id).values(revoked=True)
    )


def limitar_intentos(request: Request):
    # Registro persistente y atómico; no depende de la memoria de un worker.
    now = ahora_utc()
    ip = request.client.host if request.client else "local"
    key = resumir_token(f"{ip}:{int(now.timestamp()) // 300}")
    with SessionLocal.begin() as db:
        db.execute(delete(LimiteIntentos).where(LimiteIntentos.expires_at < now))
        stmt = (
            insert(LimiteIntentos)
            .values(key=key, count=1, expires_at=now + timedelta(minutes=10))
            .on_conflict_do_update(
                index_elements=[LimiteIntentos.key],
                set_={"count": LimiteIntentos.count + 1},
            )
            .returning(LimiteIntentos.count)
        )
        count = db.scalar(stmt)
    if count > 20:
        raise HTTPException(
            429,
            "Demasiados intentos. Espera cinco minutos.",
            headers={"Retry-After": "300"},
        )
