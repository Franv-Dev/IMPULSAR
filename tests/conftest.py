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

from config import TestingConfig
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


@pytest.fixture(scope="session", autouse=True)
def carpetas_de_subida(tmp_path_factory):
    """Manda las subidas de TODA la corrida a un temporal, no al repo.

    TestingConfig no definia UPLOAD_FOLDER propio, asi que heredaba el de
    Config: static/uploads, la carpeta real. Los tests que suben imagenes de
    verdad (la galeria del blog, el avatar y la portada del perfil) escribian
    ahi archivos que nadie borra, y se iban acumulando corrida tras corrida.

    Se parchea la clase de config y no app.config porque no todos los tests
    usan la fixture `app`: varios llaman a create_app("testing") por su cuenta.
    Parcheando el origen, cualquier app de testing nace apuntando al temporal.

    Es de sesion y no por test a proposito: hay tests que comparan el contenido
    de la carpeta antes y despues (ver _archivos_en_uploads en test_blog.py), y
    con una carpeta distinta por test esa comparacion no probaria nada. Una
    sola carpeta estable toda la corrida mantiene el antes/despues honesto y
    igual no ensucia el repo.

    La estructura imita la del proyecto (publica adentro de un static/, privada
    hermana afuera) para que lo que dependa de esa relacion siga valiendo.
    """
    raiz = tmp_path_factory.mktemp("subidas")
    publica = raiz / "static" / "uploads"
    privada = raiz / "uploads_privados"
    publica.mkdir(parents=True)
    privada.mkdir()

    with pytest.MonkeyPatch.context() as parche:
        parche.setattr(TestingConfig, "UPLOAD_FOLDER", str(publica))
        parche.setattr(TestingConfig, "PRIVATE_UPLOAD_FOLDER", str(privada))
        yield
