"""Pruebas reproducibles con muestras, separadas de la consulta real documentada."""

from datetime import timedelta
import json
import uuid
import pytest
from sqlalchemy import select, func
from app.core.db import SessionLocal
from app.models import (
    Usuario,
    FuenteExterna,
    PublicacionExterna,
    AlertaHogar,
    EjecucionSincronizacion,
    ahora_utc,
)
from app.fuentes.adaptadores import (
    AdaptadorSedapar,
    AdaptadorCisternas,
    AdaptadorManosUnidas,
    ResultadoConsulta,
    PublicacionImportada,
    extraer_aviso_oficial,
    fecha_lima,
    reconocer_distritos,
)
from app.services.fuentes import (
    importar_resultado,
    sincronizar_fuentes,
    vigencia_publicacion,
    generar_alertas,
)
from conftest import register, home, container


class ClienteMuestra:
    def __init__(self, cuerpo):
        self.cuerpo = cuerpo

    def descargar(self, url):
        return self.cuerpo


def fuente(db, adaptador=None):
    a = adaptador or AdaptadorSedapar()
    f = FuenteExterna(
        clave=a.clave,
        nombre=a.nombre,
        tipo=a.tipo,
        url=a.url,
        intervalo_minutos=30,
        ultimo_exito=ahora_utc(),
        error="",
    )
    db.add(f)
    db.flush()
    return a


def aviso(db, inicio=None, fin=None, revision="automatico", categoria="corte"):
    a = fuente(db)
    p = PublicacionImportada(
        categoria=categoria,
        identificador="caso-de-prueba",
        revision=revision,
        datos={
            "titulo": "MUESTRA DE PRUEBA: corte simulado",
            "url": "https://www.gob.pe/institucion/sedapar/noticias",
            "distritos": ["Cerro Colorado"],
            "inicio": (inicio or ahora_utc() + timedelta(hours=24)).isoformat(),
            "fin_estimado": (fin or ahora_utc() + timedelta(hours=48)).isoformat(),
            "zonas": "Sector de prueba",
            "circuitos": "N-24",
        },
    )
    importar_resultado(db, a, ResultadoConsulta([p]))
    db.flush()
    return db.scalar(select(PublicacionExterna))


def test_parseo_oficial_no_confunde_publicacion_y_corte():
    html = """<main><h1>Interrupción programada 123-2026</h1><p>20 de noviembre de 2026 - 6:00 p. m.</p><p>Motivo: Limpieza</p><p>Fecha y hora de cierre: 27/11/2026 – 06:00 h</p><p>Fecha y hora aproximada de reposición: 27/11/2026 – 18:00 h</p><p>Distrito(s): Cerro Colorado</p><p>Circuito(s): N-24</p><p>Zonas afectadas: Sector de prueba</p></main>"""
    p = extraer_aviso_oficial(html, "https://www.gob.pe/aviso")
    assert p.datos["publicado"] == "2026-11-20T18:00:00-05:00"
    assert p.datos["inicio"] == "2026-11-27T06:00:00-05:00"
    assert p.datos["distritos"] == ["Cerro Colorado"] and p.revision == "automatico"
    assert (
        extraer_aviso_oficial(
            html.replace("Cerro Colorado", "Mollendo"), "https://www.gob.pe/aviso"
        )
        is None
    )


def test_fecha_invalida_no_se_inventa_y_catalogo_es_provincia():
    assert fecha_lima("31/02/2026 – 09:00 h") is None
    assert fecha_lima("2026-11-25 08:00:00").endswith("-05:00")
    assert reconocer_distritos("MOLLENDO, PEDREGAL") == []
    assert reconocer_distritos("SAN JUAN DE MIRAFLORES, LIMA CERCADO") == []
    assert reconocer_distritos("SABANDÍA") == ["Sabandía"]


def test_importacion_repetida_no_duplica_y_preserva_revision_local():
    with SessionLocal.begin() as db:
        a = fuente(db)
        p = PublicacionImportada(
            categoria="orientacion",
            identificador="ong",
            datos={
                "titulo": "Agua",
                "url": "https://www.manosunidas.org/que-hacemos/agua",
            },
        )
        assert importar_resultado(db, a, ResultadoConsulta([p])) == (1, 0)
        fila = db.scalar(select(PublicacionExterna))
        fila.revision = "aprobado"
        db.flush()
        assert importar_resultado(db, a, ResultadoConsulta([p])) == (0, 0)
        assert db.scalar(select(func.count()).select_from(PublicacionExterna)) == 1
        assert fila.revision == "aprobado"
        p.datos = {**p.datos, "titulo": "Agua actualizada"}
        assert importar_resultado(db, a, ResultadoConsulta([p])) == (0, 1)


def test_cisterna_historica_y_sin_coordenadas_inventadas():
    datos = {
        "ok": True,
        "data": [
            {
                "fecha": "2024-02-16",
                "zona_reparto": "Referencia de muestra",
                "aviso": "1",
                "distrito": "CAYMA",
                "hora_inicio": "08:00",
            }
        ],
    }
    resultado = AdaptadorCisternas().consultar(ClienteMuestra(json.dumps(datos)))
    p = resultado.publicaciones[0]
    assert p.datos["latitud"] is None and p.revision == "pendiente"
    with SessionLocal.begin() as db:
        a = fuente(db, AdaptadorCisternas())
        importar_resultado(db, a, resultado)
        assert (
            vigencia_publicacion(db.scalar(select(PublicacionExterna))) == "historico"
        )


def test_fuente_caida_conserva_registros_y_ultimo_exito():
    class FuenteCaida(AdaptadorSedapar):
        def consultar(self, cliente):
            raise ValueError("Fuente fuera de servicio (prueba)")

    with SessionLocal.begin() as db:
        aviso(db)
        f = db.get(FuenteExterna, "sedapar_gob")
        fecha = f.ultimo_exito
    resultado = sincronizar_fuentes(
        forzar=True, adaptadores=[FuenteCaida()], cliente=ClienteMuestra("")
    )
    assert resultado[0]["estado"] == "error"
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(PublicacionExterna)) == 1
        assert db.get(FuenteExterna, "sedapar_gob").ultimo_exito == fecha
        assert db.scalar(select(EjecucionSincronizacion)).estado == "error"


def test_alertas_no_se_duplican_y_no_se_envian_ambiguas(client):
    user, headers = register(client)
    home(client, headers)
    with SessionLocal.begin() as db:
        p = aviso(db, revision="pendiente")
        generar_alertas(db)
        assert db.scalar(select(func.count()).select_from(AlertaHogar)) == 0
        p.revision = "aprobado"
        db.flush()
        generar_alertas(db)
        generar_alertas(db)
        assert db.scalar(select(func.count()).select_from(AlertaHogar)) == 1
    lista = client.get("/api/v1/alertas").json()
    assert len(lista) == 1
    assert (
        client.post(
            "/api/v1/alertas/" + lista[0]["id"] + "/leer", headers=headers
        ).status_code
        == 200
    )
    assert client.get("/api/v1/alertas").json()[0]["leida"] is True


def test_evaluacion_futura_descuenta_consumo_sin_modificar_saldos(client):
    user, headers = register(client)
    home(client, headers, drinking=24, other=48)
    container(client, headers, balance=40, capacity=60)
    with SessionLocal.begin() as db:
        p = aviso(db)
        id = str(p.id)
    r = client.post(
        f"/api/v1/publicaciones/{id}/evaluar", headers=headers, json={}
    ).json()
    assert r["actual"]["items"][0]["available"] == 40
    assert r["proyeccion_inicio"]["items"][0]["available"] == pytest.approx(
        16, abs=0.02
    )
    assert "Posible afectación" in r["coincidencia"]
    assert client.get("/api/v1/recipientes").json()[0]["balance"] == 40
    guardado = client.post(
        f"/api/v1/publicaciones/{id}/guardar-plan",
        headers=headers,
        json={"version_datos": r["actual"]["data_version"]},
    )
    assert (
        guardado.status_code == 200 and guardado.json()["snapshot"]["aviso"]["id"] == id
    )
    assert client.get("/api/v1/recipientes").json()[0]["balance"] == 40
    assert (
        client.post(
            f"/api/v1/publicaciones/{id}/guardar-plan",
            headers=headers,
            json={"version_datos": 0},
        ).status_code
        == 409
    )


def test_pasado_requiere_escenario_manual_y_listado_filtra(client):
    u, h = register(client)
    home(client, h)
    with SessionLocal.begin() as db:
        p = aviso(
            db,
            inicio=ahora_utc() - timedelta(days=2),
            fin=ahora_utc() - timedelta(days=1),
        )
        id = str(p.id)
    assert client.get("/api/v1/publicaciones").json()["registros"] == []
    lista = client.get("/api/v1/publicaciones?historicos=true").json()["registros"]
    assert len(lista) == 1
    assert lista[0]["vigencia"] == "plazo_estimado_pasado"
    assert (
        client.post(
            f"/api/v1/publicaciones/{id}/evaluar", headers=h, json={}
        ).status_code
        == 422
    )
    assert (
        client.post(
            f"/api/v1/publicaciones/{id}/evaluar",
            headers=h,
            json={"horas_manuales": 24},
        ).json()["manual"]
        is True
    )


def test_revision_exige_admin_csrf_y_coordenadas_respaldadas(client):
    u, h = register(client)
    with SessionLocal.begin() as db:
        p = aviso(db, revision="pendiente", categoria="punto")
        id = str(p.id)
    ruta = f"/api/v1/admin/fuentes/publicaciones/{id}"
    body = {"estado": "aprobado", "nota": "Verificado usando una muestra para pruebas."}
    assert client.patch(ruta, headers=h, json=body).status_code == 403
    assert (
        client.post("/api/v1/admin/fuentes/sincronizar", headers=h).status_code == 403
    )
    with SessionLocal.begin() as db:
        db.get(Usuario, uuid.UUID(u["id"])).role = "ADMIN"
    assert client.patch(ruta, json=body).status_code == 403
    assert (
        client.patch(
            ruta, headers=h, json={**body, "latitud": -16.4, "longitud": -71.5}
        ).status_code
        == 422
    )
    r = client.patch(
        ruta,
        headers=h,
        json={
            **body,
            "latitud": -16.4,
            "longitud": -71.5,
            "referencia_coordenadas": "https://www.gob.pe/referencia-muestra",
        },
    )
    assert r.status_code == 200
    with SessionLocal() as db:
        assert (
            db.get(PublicacionExterna, uuid.UUID(id)).datos["coordenadas_verificadas"]
            is True
        )


def test_ong_es_orientacion_sin_fabricar_fecha():
    html = '<title>Agua | Manos Unidas</title><meta name="description" content="Agua para la comunidad.">'
    p = AdaptadorManosUnidas().consultar(ClienteMuestra(html)).publicaciones[0]
    assert p.categoria == "orientacion" and p.datos["publicado"] is None


def test_hogares_privados_en_evaluacion_y_alertas(client):
    u, h = register(client)
    home(client, h)
    container(client, h, balance=35)
    with SessionLocal.begin() as db:
        p = aviso(db)
        id = str(p.id)
    client.post("/api/v1/auth/logout", headers=h)
    u2, h2 = register(client, email="otra@example.com")
    home(client, h2)
    container(client, h2, balance=3)
    r = client.post(
        f"/api/v1/publicaciones/{id}/evaluar", headers=h2, json={"horas_manuales": 24}
    )
    assert r.json()["actual"]["items"][0]["available"] == 3


def test_tablas_propias_en_espanol():
    from app.models import Base

    assert {
        "usuarios",
        "hogares",
        "recipientes",
        "movimientos",
        "planes",
        "sesiones",
        "eventos_auditoria",
        "fuentes_externas",
        "publicaciones_externas",
        "alertas_hogar",
    } <= set(Base.metadata.tables)
    assert not {"users", "containers", "households"} & set(Base.metadata.tables)
