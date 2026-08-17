"""Fixtures compartidas por todos los tests.

Antes cada archivo de test armaba su propia mini-app a mano, registrando solo
los blueprints que necesitaba. El problema es que asi los tests no probaban la
app real: no cubrian que todos los blueprints convivan bien, ni que las
extensiones (JWT, CSRF, migraciones) esten bien inicializadas.

Ahora se usa create_app("testing"), la misma funcion que usa produccion, pero
con la configuracion de testing (SQLite en memoria y CSRF desactivado).
"""

import pytest
from werkzeug.security import generate_password_hash

from db import db as _db
from main import create_app
from app.blog.modelo_post import Post
from models.user import Roles, User


@pytest.fixture
def app():
    """La aplicacion real, configurada para testing."""
    app = create_app("testing")

    with app.app_context():
        _db.create_all()
        yield app
        _db.session.remove()
        _db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def db(app):
    """Sesion de base de datos ya dentro del contexto de la app."""
    return _db


@pytest.fixture
def crear_usuario(db):
    """Fabrica de usuarios para los tests.

    Devuelve una funcion, asi cada test crea los usuarios que necesita sin
    repetir el mismo bloque de codigo.
    """

    def _crear(username="tomy", email=None, password="secreta123", rol=Roles.USUARIO):
        user = User(
            username=username,
            email=email or f"{username}@test.com",
            password=generate_password_hash(password),
            rol=rol,
        )
        db.session.add(user)
        db.session.commit()
        return user

    return _crear


@pytest.fixture
def crear_post(db):
    """Fabrica de emprendimientos."""

    def _crear(author_id, title="Panadería del barrio", body="Pan artesanal", **kwargs):
        post = Post(author=author_id, title=title, body=body, **kwargs)
        db.session.add(post)
        db.session.commit()
        return post

    return _crear


@pytest.fixture
def login(client):
    """Deja al cliente logueado como el usuario indicado (sesion HTML)."""

    def _login(user_id):
        with client.session_transaction() as sesion:
            sesion["user_id"] = user_id

    return _login
