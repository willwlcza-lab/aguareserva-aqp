"""Importación transaccional, deduplicación y planificación explicable."""

from datetime import datetime, timedelta
from decimal import Decimal
from hashlib import sha256
import json
import logging
import math
from types import SimpleNamespace
from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from fastapi import HTTPException
from ..core.db import engine, SessionLocal
from ..core.config import settings
from ..models import (
    FuenteExterna,
    PublicacionExterna,
    EjecucionSincronizacion,
    AlertaHogar,
    Hogar,
    ahora_utc,
)
from ..repositories import RepositorioAgua
from ..fuentes.adaptadores import ClientePublico, obtener_adaptadores, LIMA, normalizar
from .water import calcular_plan

log = logging.getLogger(__name__)


def vigencia_publicacion(publicacion, ahora=None):
    """Tiempo anunciado, no estado físico del servicio ni garantía de atención."""
    datos = publicacion.datos
    ahora = (ahora or ahora_utc()).astimezone(LIMA)
    if publicacion.categoria == "orientacion":
        return "orientacion_general"
    if publicacion.categoria == "punto":
        fecha = datos.get("fecha_atencion")
        if not fecha:
            return "vigencia_no_confirmada"
        if fecha < ahora.date().isoformat():
            return "historico"
        return (
            "anunciado_hoy_sin_confirmar"
            if fecha == ahora.date().isoformat()
            else "anunciado_futuro"
        )
    inicio = datos.get("inicio")
    fin = datos.get("fin_estimado")
    if inicio and datetime.fromisoformat(inicio) > ahora:
        return "programado"
    if fin and datetime.fromisoformat(fin) < ahora:
        return "plazo_estimado_pasado"
    if inicio and fin:
        return "en_horario_anunciado"
    return "horario_desconocido"


def coincidencia_hogar(publicacion, hogar):
    if not hogar or hogar.district not in publicacion.datos.get("distritos", []):
        return None
    sector = normalizar(hogar.sector)
    detalle = normalizar(
        publicacion.datos.get("zonas", "")
        + " "
        + publicacion.datos.get("circuitos", "")
    )
    if len(sector) >= 4 and sector in detalle:
        return "Coinciden distrito y texto del sector; verifica el comunicado."
    return "Posible afectación por distrito; no confirma que tu vivienda esté incluida."


def generar_alertas(db):
    hogares = list(db.scalars(select(Hogar)))
    avisos = db.scalars(
        select(PublicacionExterna).where(
            PublicacionExterna.categoria == "corte",
            PublicacionExterna.revision.in_(["automatico", "aprobado"]),
        )
    )
    for aviso in avisos:
        if vigencia_publicacion(aviso) not in ("programado", "en_horario_anunciado"):
            continue
        if aviso.datos.get("inicio") and datetime.fromisoformat(
            aviso.datos["inicio"]
        ) > ahora_utc() + timedelta(days=7):
            continue
        for hogar in hogares:
            if coincidencia_hogar(aviso, hogar):
                db.execute(
                    insert(AlertaHogar)
                    .values(hogar_id=hogar.id, publicacion_id=aviso.id)
                    .on_conflict_do_nothing(constraint="uq_alerta_hogar_aviso")
                )


def importar_resultado(db, adaptador, resultado):
    nuevos = actualizados = 0
    for entrada in resultado.publicaciones:
        clave = sha256(
            (entrada.categoria + "|" + entrada.identificador).encode()
        ).hexdigest()
        huella = sha256(
            json.dumps(entrada.datos, ensure_ascii=False, sort_keys=True).encode()
        ).hexdigest()
        anterior = db.scalar(
            select(PublicacionExterna).where(
                PublicacionExterna.fuente_clave == adaptador.clave,
                PublicacionExterna.clave_origen == clave,
            )
        )
        if anterior:
            anterior.consultado = ahora_utc()
            if anterior.hash_contenido != huella:
                anterior.datos = entrada.datos
                anterior.hash_contenido = huella
                anterior.actualizado = ahora_utc()
                # Si cambió el origen, una aprobación anterior ya no valida el contenido nuevo.
                anterior.revision = entrada.revision
                anterior.observacion = entrada.observacion
                actualizados += 1
        else:
            db.add(
                PublicacionExterna(
                    fuente_clave=adaptador.clave,
                    clave_origen=clave,
                    categoria=entrada.categoria,
                    datos=entrada.datos,
                    hash_contenido=huella,
                    revision=entrada.revision,
                    observacion=entrada.observacion,
                )
            )
            nuevos += 1
    db.flush()
    generar_alertas(db)
    return nuevos, actualizados


def sincronizar_fuentes(forzar=False, adaptadores=None, cliente=None):
    """Un candado PostgreSQL evita sincronizaciones simultáneas entre procesos.

    Cada fuente tiene su propia transacción. Una caída no revierte los éxitos
    de las otras fuentes ni elimina publicaciones anteriores.
    """
    resultados = []
    propio = cliente is None
    with engine.connect() as candado:
        if not candado.scalar(text("SELECT pg_try_advisory_lock(786245011)")):
            return [
                {
                    "estado": "ocupado",
                    "detalle": "Ya hay una sincronización en ejecución.",
                }
            ]
        try:
            if propio:
                cliente = ClientePublico()
            for adaptador in adaptadores or obtener_adaptadores():
                intervalo = getattr(
                    settings, adaptador.clave + "_minutos", adaptador.intervalo
                )
                with SessionLocal.begin() as db:
                    fuente = db.get(FuenteExterna, adaptador.clave)
                    if not fuente:
                        fuente = FuenteExterna(
                            clave=adaptador.clave,
                            nombre=adaptador.nombre,
                            tipo=adaptador.tipo,
                            url=adaptador.url,
                            intervalo_minutos=intervalo,
                        )
                        db.add(fuente)
                    fuente.intervalo_minutos = intervalo
                    if (
                        fuente.ultimo_intento
                        and fuente.ultimo_intento
                        > ahora_utc() - timedelta(minutes=1 if forzar else intervalo)
                    ):
                        continue
                    fuente.ultimo_intento = ahora_utc()
                    db.flush()
                    # Una ejecución abandonada por apagado queda documentada en el próximo arranque.
                    for pendiente in db.scalars(
                        select(EjecucionSincronizacion).where(
                            EjecucionSincronizacion.fuente_clave == adaptador.clave,
                            EjecucionSincronizacion.estado == "en_progreso",
                        )
                    ):
                        pendiente.estado = "interrumpida"
                        pendiente.finalizado = ahora_utc()
                        pendiente.detalle = "El proceso anterior se cerró antes de completar la consulta."
                    ejecucion = EjecucionSincronizacion(fuente_clave=adaptador.clave)
                    db.add(ejecucion)
                    db.flush()
                    identificador = ejecucion.id
                try:
                    resultado = adaptador.consultar(cliente)
                    with SessionLocal.begin() as db:
                        nuevos, actualizados = importar_resultado(
                            db, adaptador, resultado
                        )
                        fuente = db.get(FuenteExterna, adaptador.clave)
                        fuente.ultimo_exito = ahora_utc()
                        fuente.error = "\n".join(resultado.advertencias)[:4000]
                        ejecucion = db.get(EjecucionSincronizacion, identificador)
                        ejecucion.estado = (
                            "parcial" if resultado.advertencias else "correcta"
                        )
                        ejecucion.finalizado = ahora_utc()
                        ejecucion.nuevos = nuevos
                        ejecucion.actualizados = actualizados
                        ejecucion.detalle = fuente.error
                        resultados.append(
                            {
                                "fuente": adaptador.clave,
                                "estado": ejecucion.estado,
                                "nuevos": nuevos,
                                "actualizados": actualizados,
                            }
                        )
                except Exception as error:
                    log.warning("Fallo en %s: %s", adaptador.clave, error)
                    with SessionLocal.begin() as db:
                        fuente = db.get(FuenteExterna, adaptador.clave)
                        fuente.error = str(error)[:2000]
                        ejecucion = db.get(EjecucionSincronizacion, identificador)
                        ejecucion.estado = "error"
                        ejecucion.finalizado = ahora_utc()
                        ejecucion.detalle = fuente.error
                    resultados.append({"fuente": adaptador.clave, "estado": "error"})
        finally:
            if propio and cliente:
                cliente.cerrar()
            candado.execute(text("SELECT pg_advisory_unlock(786245011)"))
            candado.commit()
    return resultados


def vista_publicacion(p, fuente, hogar=None):
    return {
        "id": str(p.id),
        "categoria": p.categoria,
        "datos": p.datos,
        "revision": p.revision,
        "observacion": p.observacion,
        "consultado": p.consultado,
        "actualizado": p.actualizado,
        "vigencia": vigencia_publicacion(p),
        "fuente": {"nombre": fuente.nombre, "tipo": fuente.tipo},
        "coincidencia": coincidencia_hogar(p, hogar),
        "fuente_desactualizada": not fuente.ultimo_exito
        or bool(fuente.error)
        or fuente.ultimo_exito
        < ahora_utc() - timedelta(minutes=fuente.intervalo_minutos * 2),
    }


def evaluar_reservas(db, usuario, publicacion, horas_manuales=None):
    repo = RepositorioAgua(db)
    hogar = repo.obtener_hogar(usuario.id)
    recipientes = repo.listar_recipientes(hogar.id)
    d = publicacion.datos
    ahora = ahora_utc()
    inicio = datetime.fromisoformat(d["inicio"]) if d.get("inicio") else None
    fin = datetime.fromisoformat(d["fin_estimado"]) if d.get("fin_estimado") else None
    manual = horas_manuales is not None
    if not manual and (not inicio or not fin or fin <= ahora or fin <= inicio):
        raise HTTPException(
            422,
            "El horario es desconocido o ya pasó. Indica horas para un escenario manual; no significa que el servicio se haya restablecido.",
        )
    horas = (
        horas_manuales
        if manual
        else max(1, math.ceil((fin - max(inicio, ahora)).total_seconds() / 3600))
    )
    if not 1 <= horas <= 720:
        raise HTTPException(422, "Usa un escenario manual de 1 a 720 horas.")
    actual = calcular_plan(hogar, recipientes, horas)
    espera = (
        0 if manual or not inicio else max(0, (inicio - ahora).total_seconds() / 3600)
    )
    proyectados = []
    agotamiento_antes = False
    for tipo, diario in [
        ("drinking", hogar.drinking_daily),
        ("other", hogar.other_daily),
    ]:
        grupo = [r for r in recipientes if r.water_type == tipo]
        saldo = sum((r.balance for r in grupo), Decimal(0))
        capacidad = sum((r.capacity for r in grupo), Decimal(0))
        consumo = Decimal(str(espera)) * diario / 24 if diario is not None else None
        estimado = max(Decimal(0), saldo - consumo) if consumo is not None else saldo
        if consumo is not None and consumo > saldo:
            agotamiento_antes = True
        proyectados.append(
            SimpleNamespace(water_type=tipo, balance=estimado, capacity=capacidad)
        )
    proyeccion = calcular_plan(hogar, proyectados, horas) if espera > 0 else None
    supuesto = (
        "Escenario manual; no representa un corte vigente."
        if manual
        else "Duración anunciada o restante, redondeada hacia arriba a horas completas."
    )
    if espera:
        supuesto += " La proyección descuenta el consumo declarado hasta el inicio, sin recargas futuras. Si falta consumo declarado, ese uso sigue sin estimación."
    actual["basis"] = supuesto
    if proyeccion:
        proyeccion["basis"] = supuesto
    return {
        "horas": horas,
        "manual": manual,
        "coincidencia": coincidencia_hogar(publicacion, hogar),
        "actual": actual,
        "proyeccion_inicio": proyeccion,
        "horas_hasta_inicio": round(espera, 2),
        "agotamiento_antes": agotamiento_antes,
        "supuesto": supuesto,
        "advertencia": "La coincidencia de distrito y las horas estimadas no confirman la situación de tu vivienda. No se modificaron tus saldos.",
        "fuente_pendiente": publicacion.revision == "pendiente",
        "aviso_id": str(publicacion.id),
    }
