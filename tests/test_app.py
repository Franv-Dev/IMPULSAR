"""Tests del armado de la aplicacion: configuracion, CSRF y paginas de error.

Estos casos no existian porque antes no habia forma de crear la app con otra
configuracion: se creaba sola al importar main.
"""

import pytest
from flask import Flask

from config import DevelopmentConfig, ProductionConfig, TestingConfig, get_config
from db import db as _db
from main import create_app


# ------------------------------------------------------------- configuracion

def test_get_config_devuelve_la_clase_correcta():
    assert get_config("testing") is TestingConfig
    assert get_config("development") is DevelopmentConfig
    assert get_config("production") is ProductionConfig


def test_un_entorno_desconocido_cae_en_desarrollo():
    assert get_config("una-cosa-rara") is DevelopmentConfig


def test_la_app_de_testing_usa_sqlite_en_memoria():
    app = create_app("testing")

    assert app.config["TESTING"] is True
    assert app.config["SQLALCHEMY_DATABASE_URI"] == "sqlite:///:memory:"


def test_produccion_no_arranca_sin_claves():
    """Antes las claves tenian un default hardcodeado y la app arrancaba igual."""
    app = Flask(__name__)
    app.config["SECRET_KEY"] = None
    app.config["JWT_SECRET_KEY"] = None

    with pytest.raises(RuntimeError) as error:
        ProductionConfig.init_app(app)

    assert "SECRET_KEY" in str(error.value)
    assert "JWT_SECRET_KEY" in str(error.value)


def test_produccion_arranca_con_las_claves_puestas():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "una-clave-real"
    app.config["JWT_SECRET_KEY"] = "otra-clave-real"

    ProductionConfig.init_app(app)  # no debe lanzar


def test_se_pueden_crear_dos_apps_a_la_vez():
    """Es justamente lo que permite el patron factory."""
    una = create_app("testing")
    otra = create_app("testing")

    assert una is not otra


# --------------------------------------------------------------------- CSRF

@pytest.fixture
def app_con_csrf():
    app = create_app("testing")
    app.config["WTF_CSRF_ENABLED"] = True

    with app.app_context():
        _db.create_all()
        yield app
        _db.session.remove()
        _db.drop_all()


def test_el_formulario_sin_token_csrf_es_rechazado(app_con_csrf):
    client = app_con_csrf.test_client()

    resp = client.post("/auth/login", data={"username": "x", "password": "y"})

    # El handler de CSRFError redirige con un mensaje en vez de un 400 crudo.
    assert resp.status_code == 303


def test_los_formularios_incluyen_el_token_csrf(app_con_csrf):
    client = app_con_csrf.test_client()

    for url in ("/auth/login", "/auth/register"):
        html = client.get(url).get_data(as_text=True)
        assert 'name="csrf_token"' in html, f"Falta el token en {url}"


def test_la_api_json_sigue_funcionando_con_csrf_activo(app_con_csrf):
    """La API se autentica por header, no por cookie: exigirle token la romperia."""
    client = app_con_csrf.test_client()

    resp = client.post("/auth/api/register", json={
        "username": "tomy", "email": "tomy@test.com", "password": "secreta123",
    })

    assert resp.status_code == 201


# ------------------------------------------------------------ paginas de error

def test_pagina_404_personalizada(client):
    resp = client.get("/una-url-que-no-existe")

    assert resp.status_code == 404
    assert "No encontramos esta página" in resp.get_data(as_text=True)


def test_el_limite_de_subida_esta_configurado(app):
    assert app.config["MAX_CONTENT_LENGTH"] == 5 * 1024 * 1024
