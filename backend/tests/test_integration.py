import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from fastapi.testclient import TestClient
from sqlalchemy import select, func
from app.main import app
from app.core.db import SessionLocal
from app.core.security import resumir_token
from app.core.config import settings
from app.models import Usuario, Hogar, Movimiento, SesionAcceso, ahora_utc
from app.services.water import ServicioAgua
from app.schemas import DatosMovimiento
from conftest import validar_csrf, register, home, container


def registrar_movimiento(
    c, headers, container_id, kind="consumption", liters=5, key=None, reason=""
):
    return c.post(
        f"/api/v1/recipientes/{container_id}/movimientos",
        headers=headers,
        json={
            "kind": kind,
            "liters": liters,
            "reason": reason,
            "idempotency_key": str(key or uuid.uuid4()),
        },
    )


def test_registration_hash_role_and_session_cookie(client):
    u, h = register(client)
    assert u["role"] == "USER"
    assert "password_hash" not in u
    assert client.get("/api/v1/auth/me").json()["id"] == u["id"]
    with SessionLocal() as db:
        user = db.get(Usuario, uuid.UUID(u["id"]))
        assert user.password_hash.startswith("$argon2")
    r = client.get("/api/v1/admin/resumen")
    assert r.status_code == 403
    assert (
        client.post(
            "/api/v1/hogares", json={"name": "Xx", "district": "Cayma", "members": 1}
        ).status_code
        == 403
    )


def test_csrf_cookie_rotation_and_logout(client):
    client.get("/api/v1/auth/csrf")
    old = client.cookies.get(settings.cookie_name)
    _, headers = register(client)
    token = client.cookies.get(settings.cookie_name)
    assert old != token
    assert client.post("/api/v1/auth/logout", headers=headers).status_code == 200
    client.cookies.set(settings.cookie_name, token)
    assert client.get("/api/v1/auth/me").status_code == 401


def test_role_injection_is_rejected(client):
    r = client.post(
        "/api/v1/auth/registro",
        headers=validar_csrf(client),
        json={
            "name": "Ana",
            "email": "ana@example.com",
            "password": "Una clave larga",
            "role": "ADMIN",
        },
    )
    assert r.status_code == 422
    assert "Una clave larga" not in r.text


def test_email_unique_case_insensitive(client):
    register(client, email="ana@example.com")
    r = client.post(
        "/api/v1/auth/registro",
        headers=validar_csrf(client),
        json={
            "name": "Otra",
            "email": "ANA@example.com",
            "password": "Una clave larga",
        },
    )
    assert r.status_code == 409


def test_expired_session_denied(client):
    register(client)
    token = client.cookies.get(settings.cookie_name)
    with SessionLocal.begin() as db:
        s = db.scalar(
            select(SesionAcceso).where(SesionAcceso.token_hash == resumir_token(token))
        )
        s.last_seen = ahora_utc() - timedelta(hours=1)
    assert client.get("/api/v1/auth/me").status_code == 401


def test_one_household_per_user(client):
    _, h = register(client)
    home(client, h)
    r = client.post(
        "/api/v1/hogares",
        headers=h,
        json={"name": "Otro hogar", "district": "Cayma", "members": 2},
    )
    assert r.status_code == 409


def test_district_catalog_contains_all_province_districts(client):
    response = client.get("/api/v1/catalogos/distritos")
    assert response.status_code == 200
    districts = response.json()
    assert len(districts) == len(set(districts)) == 29
    assert {
        "Chiguata",
        "Mollebaya",
        "Pocsi",
        "Polobaya",
        "Quequeña",
        "Sabandía",
        "San Juan de Siguas",
        "San Juan de Tarucani",
        "Santa Isabel de Siguas",
        "Santa Rita de Siguas",
        "Uchumayo",
        "Vítor",
        "Yarabamba",
        "La Joya",
    }.issubset(districts)


def test_district_selection_creates_and_updates_home(client):
    _, headers = register(client)
    payload = {
        "name": "Hogar de prueba",
        "district": "San Juan de Tarucani",
        "members": 3,
    }
    created = client.post("/api/v1/hogares", headers=headers, json=payload)
    assert created.status_code == 201
    assert created.json()["district"] == "San Juan de Tarucani"
    # Every value published by the API must be accepted on an existing home.
    for district in client.get("/api/v1/catalogos/distritos").json():
        payload["district"] = district
        updated = client.patch("/api/v1/hogares/mio", headers=headers, json=payload)
        assert updated.status_code == 200, updated.text
        assert updated.json()["district"] == district
        assert updated.json()["id"] == created.json()["id"]


def test_invalid_district_cannot_create_a_household(client):
    _, headers = register(client)
    for district in ("", "Cerro Coloraddo", "Lima", "Mollendo", None):
        response = client.post(
            "/api/v1/hogares",
            headers=headers,
            json={"name": "Hogar de prueba", "district": district, "members": 3},
        )
        assert response.status_code == 422, response.text
        assert any(error["field"] == "district" for error in response.json()["errors"])
        assert client.get("/api/v1/hogares/mio").json() is None


def test_invalid_district_cannot_overwrite_existing_household(client):
    _, headers = register(client)
    original = home(client, headers)
    for district in ("Cerro Coloraddo", "Distrito inventado", "Lima", ""):
        response = client.patch(
            "/api/v1/hogares/mio",
            headers=headers,
            json={"name": "Cambiar nombre", "district": district, "members": 99},
        )
        assert response.status_code == 422, response.text
        assert client.get("/api/v1/hogares/mio").json() == original


def test_legacy_district_can_be_corrected_without_replacing_household(client):
    _, headers = register(client)
    original = home(client, headers)
    with SessionLocal.begin() as db:
        record = db.get(Hogar, uuid.UUID(original["id"]))
        record.district = "Cerro Coloraddo"
    assert client.get("/api/v1/hogares/mio").json()["district"] == "Cerro Coloraddo"
    response = client.patch(
        "/api/v1/hogares/mio",
        headers=headers,
        json={
            "name": original["name"],
            "district": "Cerro Colorado",
            "members": original["members"],
            "drinking_daily": 12,
            "other_daily": 60,
        },
    )
    assert response.status_code == 200
    corrected = response.json()
    assert corrected["id"] == original["id"]
    assert corrected["district"] == "Cerro Colorado"
    assert corrected["members"] == original["members"]


def test_foreign_household_access_denied(client):
    _, h = register(client)
    home(client, h)
    c = container(client, h)
    with TestClient(app) as other:
        _, oh = register(other, email="otro@example.com")
        home(other, oh)
        assert other.get("/api/v1/recipientes").json() == []
        assert registrar_movimiento(other, oh, c["id"]).status_code == 404
        assert (
            other.patch(
                f"/api/v1/recipientes/{c['id']}",
                headers=oh,
                json={"name": "No mío", "capacity": 99},
            ).status_code
            == 404
        )


def test_negative_over_capacity_and_adjustment_reason(client):
    _, h = register(client)
    home(client, h)
    c = container(client, h)
    assert registrar_movimiento(client, h, c["id"], liters=21).status_code == 409
    assert (
        registrar_movimiento(client, h, c["id"], kind="refill", liters=31).status_code
        == 409
    )
    assert registrar_movimiento(client, h, c["id"], liters=-1).status_code == 422
    assert (
        registrar_movimiento(
            client, h, c["id"], kind="adjust_down", reason=""
        ).status_code
        == 422
    )
    assert client.get("/api/v1/recipientes").json()[0]["balance"] == 20


def test_idempotency_reuses_result_and_detects_changed_payload(client):
    _, h = register(client)
    home(client, h)
    c = container(client, h)
    key = uuid.uuid4()
    first = registrar_movimiento(client, h, c["id"], key=key)
    second = registrar_movimiento(client, h, c["id"], key=key)
    assert first.json() == second.json()
    assert (
        registrar_movimiento(client, h, c["id"], key=key, liters=6).status_code == 409
    )
    assert client.get("/api/v1/recipientes").json()[0]["balance"] == 15
    with SessionLocal() as db:
        assert (
            db.scalar(select(func.count()).select_from(Movimiento)) == 2
        )  # inicial + consumo


def test_transaction_concurrency_cannot_overdraw(client):
    u, h = register(client)
    home(client, h)
    c = container(client, h)

    def consume():
        with SessionLocal() as db:
            user = db.get(Usuario, uuid.UUID(u["id"]))
            try:
                ServicioAgua(db).registrar_movimiento(
                    user,
                    uuid.UUID(c["id"]),
                    DatosMovimiento(
                        kind="consumption", liters=15, idempotency_key=uuid.uuid4()
                    ),
                )
                db.commit()
                return 200
            except Exception as e:
                db.rollback()
                return getattr(e, "status_code", 500)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: consume(), range(2)))
    assert sorted(results) == [200, 409]
    assert client.get("/api/v1/recipientes").json()[0]["balance"] == 5


def test_ledger_balance_and_archive_history(client):
    _, h = register(client)
    home(client, h)
    c = container(client, h)
    assert (
        client.post(f"/api/v1/recipientes/{c['id']}/archivar", headers=h).status_code
        == 409
    )
    assert (
        registrar_movimiento(client, h, c["id"], kind="refill", liters=5).status_code
        == 200
    )
    assert registrar_movimiento(client, h, c["id"], liters=25).status_code == 200
    assert (
        client.post(f"/api/v1/recipientes/{c['id']}/archivar", headers=h).status_code
        == 200
    )
    assert client.get("/api/v1/recipientes").json() == []
    assert len(client.get("/api/v1/movimientos").json()) == 3
    assert registrar_movimiento(client, h, c["id"], kind="refill").status_code == 409


def test_plan_distinguishes_water_types_and_capacity(client):
    _, h = register(client)
    home(client, h, drinking=10, other=20)
    container(client, h, capacity=15, balance=10)
    container(client, h, water_type="other", capacity=500, balance=300)
    p = client.post(
        "/api/v1/planes/simular", headers=h, json={"hours": 48, "reduction_percent": 50}
    ).json()
    drinking, other = p["items"]
    assert drinking["required"] == 20 and drinking["deficit"] == 10
    assert drinking["fillable"] == 5 and drinking["extra_capacity"] == 5
    assert other["required"] == 20 and other["deficit"] == 0
    assert p["status"] == "deficit"  # No compensa agua de beber con otros usos.


def test_plan_missing_and_zero_do_not_claim_infinite_autonomy(client):
    _, h = register(client)
    home(client, h, drinking=None, other=0)
    p = client.post("/api/v1/planes/simular", headers=h, json={"hours": 24}).json()
    assert p["status"] == "incomplete"
    assert p["items"][0]["required"] is None and p["items"][0]["days"] is None
    assert p["items"][1]["days"] is None


def test_stale_plan_rejected_and_snapshot_immutable(client):
    _, h = register(client)
    home(client, h)
    c = container(client, h)
    p = client.post("/api/v1/planes/simular", headers=h, json={"hours": 48}).json()
    body = {"hours": 48, "data_version": p["data_version"]}
    saved = client.post("/api/v1/planes", headers=h, json=body)
    assert saved.status_code == 201
    registrar_movimiento(client, h, c["id"])
    assert client.post("/api/v1/planes", headers=h, json=body).status_code == 409
    history = client.get("/api/v1/planes").json()
    assert history[0]["outdated"] is True
    assert history[0]["snapshot"] == saved.json()["snapshot"]


def test_password_change_revokes_sessions(client):
    _, h = register(client)
    r = client.post(
        "/api/v1/perfil/cambiar-contrasena",
        headers=h,
        json={
            "current_password": "Una clave de prueba 2026",
            "new_password": "Otra clave larga 2026",
        },
    )
    assert r.status_code == 200
    assert client.get("/api/v1/auth/me").status_code == 401
    r = client.post(
        "/api/v1/auth/login",
        headers=validar_csrf(client),
        json={"email": "ana@example.com", "password": "Otra clave larga 2026"},
    )
    assert r.status_code == 200


def test_admin_disabling_revokes_user_and_no_self_disable(client):
    admin, h = register(client)
    with SessionLocal.begin() as db:
        db.get(Usuario, uuid.UUID(admin["id"])).role = "ADMIN"
    assert client.get("/api/v1/admin/resumen").status_code == 200
    assert (
        client.patch(
            f"/api/v1/admin/usuarios/{admin['id']}/estado",
            headers=h,
            json={"active": False},
        ).status_code
        == 409
    )
    with TestClient(app) as other:
        u, oh = register(other, email="other@example.com")
        assert (
            client.patch(
                f"/api/v1/admin/usuarios/{u['id']}/estado",
                headers=h,
                json={"active": False},
            ).status_code
            == 200
        )
        assert other.get("/api/v1/auth/me").status_code == 401


def test_public_statistics_do_not_expose_private_data(client):
    _, h = register(client)
    home(client, h)
    container(client, h)
    s = client.get("/api/v1/publico/estadisticas").json()
    assert s["households"] == 1 and s["capacity"] is None and s["districts"] is None
    assert "Hogar Demo" not in str(s) and "ana@example.com" not in str(s)


def test_csv_injection_prevented(client):
    _, h = register(client)
    home(client, h)
    c = container(client, h, name="=SUM(1,2)")
    registrar_movimiento(client, h, c["id"], reason="@malicious")
    r = client.get("/api/v1/reportes/movimientos.csv")
    assert r.status_code == 200 and "'=SUM(1,2)" in r.text and "'@malicious" in r.text


def test_login_rate_limit(client):
    headers = validar_csrf(client)
    for _ in range(20):
        assert (
            client.post(
                "/api/v1/auth/login",
                headers=headers,
                json={"email": "none@example.com", "password": "invalid"},
            ).status_code
            == 401
        )
    assert (
        client.post(
            "/api/v1/auth/login",
            headers=headers,
            json={"email": "none@example.com", "password": "invalid"},
        ).status_code
        == 429
    )
