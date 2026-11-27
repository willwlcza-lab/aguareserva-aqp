"""Pruebas de integración reales. TEST_DATABASE_URL debe apuntar a una BD vacía
cuyo nombre termine en _test. Nunca se ejecuta drop_all sobre la BD de uso."""

import os
import pytest
from sqlalchemy.engine import make_url

test_url = os.getenv("TEST_DATABASE_URL")
if not test_url or not make_url(test_url).database.endswith("_test"):
    raise RuntimeError(
        "Configura TEST_DATABASE_URL con una base PostgreSQL exclusiva terminada en _test."
    )
os.environ["DATABASE_URL"] = test_url
from app.core.db import engine, Base
from app.main import app
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def reset_database():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def validar_csrf(c):
    return {"X-CSRF-Token": c.get("/api/v1/auth/csrf").json()["csrf_token"]}


def register(c, name="Ana Demo", email="ana@example.com"):
    response = c.post(
        "/api/v1/auth/registro",
        headers=validar_csrf(c),
        json={"name": name, "email": email, "password": "Una clave de prueba 2026"},
    )
    assert response.status_code == 201, response.text
    return response.json()["user"], {"X-CSRF-Token": response.json()["csrf_token"]}


def home(c, headers, drinking=12, other=60):
    response = c.post(
        "/api/v1/hogares",
        headers=headers,
        json={
            "name": "Hogar Demo",
            "district": "Cerro Colorado",
            "members": 4,
            "drinking_daily": drinking,
            "other_daily": other,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def container(c, headers, water_type="drinking", capacity=50, balance=20, name="Bidón"):
    response = c.post(
        "/api/v1/recipientes",
        headers=headers,
        json={
            "name": name,
            "water_type": water_type,
            "capacity": capacity,
            "initial_balance": balance,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()
