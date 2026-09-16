"""Tests de los largos maximos de texto, antes de que el INSERT los vea.

El agujero que cierran: eventos, productos y servicios tenian `maxlength` en el
HTML y nada del lado del servidor. El maxlength se saltea mandando el POST a
mano, y ahi el texto largo llegaba al INSERT. Que pasa entonces depende de la
base, y esa es toda la razon de que se colara:

    SQLite  guarda el texto entero, se pase o no del largo de la columna.
    MySQL   trunca o revienta segun el sql_mode, y en modo estricto (el default
            de MySQL 8) tira DataError, que nadie atrapa y el usuario ve como
            un 500.

Por eso hay dos clases de test aca. Los de SQLite prueban la regla (que el
formulario conteste el error y no guarde nada) y corren siempre. Los del final
prueban lo que SQLite no puede probar: que la fila que se estaba armando
efectivamente NO entra en MySQL, y que la ruta contesta como formulario en vez
de morir. Sin esa segunda mitad, un test verde no diria nada sobre produccion.
"""

import os
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DataError
from werkzeug.security import generate_password_hash

from app.blog.modelo_post import Post
from app.servicios.modelo import Rubros, Service
from config import TestingConfig
from db import db as _db
from main import create_app
from models.event import Event
from models.product import Product
from models.user import Roles, User
from views.eventos import MAX_DESCRIPCION as MAX_DESCRIPCION_EVENTO
from views.eventos import MAX_LUGAR, MAX_TITULO as MAX_TITULO_EVENTO
from views.products import MAX_DESCRIPCION as MAX_DESCRIPCION_PRODUCTO
from views.products import MAX_NOMBRE
from app.servicios.reglas import (
    MAX_DESCRIPCION as MAX_DESCRIPCION_SERVICIO,
    MAX_TITULO as MAX_TITULO_SERVICIO,
    MAX_ZONA_COBERTURA,
)


@pytest.fixture
def emprendedor_con_post(crear_usuario, crear_post, login):
    """Un usuario logueado con un emprendimiento propio."""

    def _crear(username="tomy"):
        usuario = crear_usuario(username=username, rol=Roles.EMPRENDEDOR)
        post = crear_post(usuario.id)
        login(usuario.id)
        return usuario, post

    return _crear


# ------------------------------------------- los limites salen de la columna

def test_largo_de_no_acepta_una_columna_sin_largo():
    """Una columna Text no tiene tope, y sin el ValueError eso explota mas tarde y peor.

    `.type.length` vale None en un Text, y validar_largo con ese tope tira
    TypeError ("'>' not supported between int and NoneType") recien en el primer
    POST que valide ese campo, o sea un 500. Con el ValueError falla al importar el
    modulo -- al arrancar la app -- y dice que columna es.

    Hoy los ocho campos validados son String; esto existe porque
    ServiceRequest.descripcion es Text a proposito y el docstring de largo_de
    invita a usarla con cualquier columna de texto.
    """
    from app.servicios.modelo_solicitud import ServiceRequest
    from services.validation import largo_de

    assert ServiceRequest.descripcion.type.length is None, (
        "si esta columna paso a tener largo, este test perdio su caso de prueba"
    )
    with pytest.raises(ValueError, match="sin largo declarado"):
        largo_de(ServiceRequest.descripcion)


def test_los_maximos_son_los_de_las_columnas():
    """Escritos a mano se despegan la primera vez que alguien agranda una columna."""
    assert MAX_TITULO_EVENTO == Event.titulo.type.length
    assert MAX_DESCRIPCION_EVENTO == Event.descripcion.type.length
    assert MAX_LUGAR == Event.lugar.type.length
    assert MAX_NOMBRE == Product.nombre.type.length
    assert MAX_DESCRIPCION_PRODUCTO == Product.descripcion.type.length
    assert MAX_TITULO_SERVICIO == Service.titulo.type.length
    assert MAX_DESCRIPCION_SERVICIO == Service.descripcion.type.length
    assert MAX_ZONA_COBERTURA == Service.zona_cobertura.type.length


# ------------------------------------------------------------------ eventos

def _evento(post_id, **cambios):
    datos = {
        "post_id": post_id,
        "titulo": "Feria de emprendedores",
        "descripcion": "En la plaza principal",
        "lugar": "Plaza San Martín",
        "fecha": "2026-09-13",
        "hora": "10:30",
        "tipo": "feria",
    }
    datos.update(cambios)
    return datos


@pytest.mark.parametrize("campo, maximo, etiqueta", [
    ("titulo", MAX_TITULO_EVENTO, "título"),
    ("descripcion", MAX_DESCRIPCION_EVENTO, "descripción"),
    ("lugar", MAX_LUGAR, "lugar"),
])
def test_un_evento_con_un_campo_largo_no_se_guarda(
    client, emprendedor_con_post, campo, maximo, etiqueta
):
    _usuario, post = emprendedor_con_post()

    respuesta = client.post(
        "/eventos/nuevo",
        data=_evento(post.id, **{campo: "a" * (maximo + 1)}),
        follow_redirects=True,
    )

    assert respuesta.status_code == 200
    assert Event.query.count() == 0
    texto = respuesta.get_data(as_text=True)
    assert etiqueta in texto
    assert str(maximo) in texto


@pytest.mark.parametrize("campo, maximo", [
    ("titulo", MAX_TITULO_EVENTO),
    ("descripcion", MAX_DESCRIPCION_EVENTO),
    ("lugar", MAX_LUGAR),
])
def test_un_evento_justo_en_el_limite_si_se_guarda(
    client, emprendedor_con_post, campo, maximo
):
    """El limite es el largo de la columna, no uno menos."""
    _usuario, post = emprendedor_con_post()

    client.post(
        "/eventos/nuevo",
        data=_evento(post.id, **{campo: "a" * maximo}),
        follow_redirects=True,
    )

    assert getattr(Event.query.one(), campo) == "a" * maximo


def test_editar_un_evento_tampoco_deja_pasar_un_campo_largo(
    client, emprendedor_con_post
):
    """La edicion pasa por el mismo _leer_formulario, pero se prueba igual."""
    _usuario, post = emprendedor_con_post()
    client.post("/eventos/nuevo", data=_evento(post.id), follow_redirects=True)
    evento = Event.query.one()

    client.post(
        f"/eventos/{evento.id}/editar",
        data=_evento(post.id, titulo="a" * (MAX_TITULO_EVENTO + 1)),
        follow_redirects=True,
    )

    assert Event.query.one().titulo == "Feria de emprendedores"


# ---------------------------------------------------------------- productos

def _producto(post_id, **cambios):
    datos = {
        "post_id": post_id,
        "nombre": "Pan de campo",
        "descripcion": "De masa madre",
        "precio": "1.500,50",
        "disponible": "on",
    }
    datos.update(cambios)
    return datos


@pytest.mark.parametrize("campo, maximo, etiqueta", [
    ("nombre", MAX_NOMBRE, "nombre"),
    ("descripcion", MAX_DESCRIPCION_PRODUCTO, "descripción"),
])
def test_un_producto_con_un_campo_largo_no_se_guarda(
    client, emprendedor_con_post, campo, maximo, etiqueta
):
    _usuario, post = emprendedor_con_post()

    respuesta = client.post(
        "/productos/nuevo",
        data=_producto(post.id, **{campo: "a" * (maximo + 1)}),
        follow_redirects=True,
    )

    assert respuesta.status_code == 200
    assert Product.query.count() == 0
    texto = respuesta.get_data(as_text=True)
    assert etiqueta in texto
    assert str(maximo) in texto


@pytest.mark.parametrize("campo, maximo", [
    ("nombre", MAX_NOMBRE),
    ("descripcion", MAX_DESCRIPCION_PRODUCTO),
])
def test_un_producto_justo_en_el_limite_si_se_guarda(
    client, emprendedor_con_post, campo, maximo
):
    _usuario, post = emprendedor_con_post()

    client.post(
        "/productos/nuevo",
        data=_producto(post.id, **{campo: "a" * maximo}),
        follow_redirects=True,
    )

    assert getattr(Product.query.one(), campo) == "a" * maximo


# ---------------------------------------------------------------- servicios

def _servicio(post_id, **cambios):
    datos = {
        "post_id": post_id,
        "titulo": "Destapación de cañerías",
        "rubro": Rubros.PLOMERIA,
        "descripcion": "Con máquina, sin romper",
        "zona_cobertura": "Maipú y alrededores",
        "precio_estimado": "15.000,50",
        "disponible": "on",
    }
    datos.update(cambios)
    return datos


@pytest.mark.parametrize("campo, maximo, etiqueta", [
    ("titulo", MAX_TITULO_SERVICIO, "título"),
    ("descripcion", MAX_DESCRIPCION_SERVICIO, "descripción"),
    ("zona_cobertura", MAX_ZONA_COBERTURA, "zona de cobertura"),
])
def test_un_servicio_con_un_campo_largo_no_se_guarda(
    client, emprendedor_con_post, campo, maximo, etiqueta
):
    _usuario, post = emprendedor_con_post()

    respuesta = client.post(
        "/servicios/nuevo",
        data=_servicio(post.id, **{campo: "a" * (maximo + 1)}),
        follow_redirects=True,
    )

    assert respuesta.status_code == 200
    assert Service.query.count() == 0
    texto = respuesta.get_data(as_text=True)
    assert etiqueta in texto
    assert str(maximo) in texto


@pytest.mark.parametrize("campo, maximo", [
    ("titulo", MAX_TITULO_SERVICIO),
    ("descripcion", MAX_DESCRIPCION_SERVICIO),
    ("zona_cobertura", MAX_ZONA_COBERTURA),
])
def test_un_servicio_justo_en_el_limite_si_se_guarda(
    client, emprendedor_con_post, campo, maximo
):
    _usuario, post = emprendedor_con_post()

    client.post(
        "/servicios/nuevo",
        data=_servicio(post.id, **{campo: "a" * maximo}),
        follow_redirects=True,
    )

    assert getattr(Service.query.one(), campo) == "a" * maximo


# ------------------------------------------------------ contra MySQL de verdad
#
# Todo lo de arriba pasa igual con y sin la validacion en SQLite para la mitad
# que importa: SQLite se traga el texto largo sin chistar, asi que "no revienta"
# no prueba nada. Lo que sigue corre contra un MySQL real en modo estricto, que
# es donde el bug era un 500.


def _servidor_mysql():
    """La URI del MySQL local SIN base, armada como la arma config.py."""
    return (
        f"mysql+pymysql://{os.getenv('DB_USER', '')}:{os.getenv('DB_PASSWORD', '')}"
        f"@{os.getenv('DB_HOST', 'localhost')}:{os.getenv('DB_PORT', '3306')}"
    )


@pytest.fixture
def app_en_mysql():
    """La app de testing contra un MySQL de verdad, en base descartable.

    NO USA LAS FIXTURES DE conftest y arma todo de nuevo, por lo mismo que
    app_en_mysql en test_favorites.py: con aquellas, la app se destruye DESPUES
    de esta fixture y el DROP DATABASE se queda esperando para siempre a una
    conexion que todavia no se cerro.

    Se saltea el test si no hay servidor a mano (la suite corre en SQLite), y
    tambien si el sql_mode NO es estricto: sin modo estricto MySQL trunca en
    silencio en vez de fallar, y el test pasaria sin estar probando nada.
    """
    try:
        motor = create_engine(_servidor_mysql())
        conexion = motor.connect()
    except Exception as error:  # servidor apagado, credenciales, driver
        pytest.skip(f"sin MySQL local: {error}")

    base = "impulsar_test_largos"
    with conexion:
        modo = conexion.execute(text("SELECT @@SESSION.sql_mode")).scalar() or ""
        if "STRICT_TRANS_TABLES" not in modo and "STRICT_ALL_TABLES" not in modo:
            motor.dispose()
            pytest.skip(f"MySQL sin modo estricto, el test no probaria nada: {modo}")
        conexion.execute(text(f"DROP DATABASE IF EXISTS {base}"))
        conexion.execute(
            text(
                f"CREATE DATABASE {base} "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
        )

    with pytest.MonkeyPatch.context() as parche:
        parche.setattr(
            TestingConfig, "SQLALCHEMY_DATABASE_URI", f"{_servidor_mysql()}/{base}"
        )
        app = create_app("testing")

    with app.app_context():
        _db.create_all()
        client = app.test_client()

        usuario = User(
            username="tomy",
            email="tomy@test.com",
            password=generate_password_hash("secreta123"),
            rol=Roles.EMPRENDEDOR,
        )
        _db.session.add(usuario)
        _db.session.commit()
        post = Post(author=usuario.id, title="Panadería", body="Pan artesanal")
        _db.session.add(post)
        _db.session.commit()
        with client.session_transaction() as sesion:
            sesion["user_id"] = usuario.id

        yield SimpleNamespace(client=client, db=_db, post=post, usuario=usuario)

        _db.session.remove()
        motores = list(app.extensions["sqlalchemy"].engines.values())

    for motor_de_la_app in motores:
        motor_de_la_app.dispose()
    with motor.connect() as conexion:
        conexion.execute(text(f"DROP DATABASE IF EXISTS {base}"))
    motor.dispose()


def test_en_mysql_estricto_el_texto_largo_no_entra(app_en_mysql):
    """La mitad que SQLite no puede probar: la fila NO entra, revienta.

    Esto es lo que pasaba en produccion cuando el POST se mandaba a mano, y es
    lo que hace que los tests de arriba signifiquen algo: si la validacion se
    saca, el formulario llega justo hasta este INSERT.
    """
    evento = Event(
        post_id=app_en_mysql.post.id,
        titulo="a" * (MAX_TITULO_EVENTO + 1),
        fecha="2026-09-13",
    )
    app_en_mysql.db.session.add(evento)

    with pytest.raises(DataError):
        app_en_mysql.db.session.commit()

    app_en_mysql.db.session.rollback()


@pytest.mark.parametrize("ruta, datos, modelo, campo, maximo", [
    ("/eventos/nuevo", _evento, Event, "titulo", MAX_TITULO_EVENTO),
    ("/eventos/nuevo", _evento, Event, "descripcion", MAX_DESCRIPCION_EVENTO),
    ("/eventos/nuevo", _evento, Event, "lugar", MAX_LUGAR),
    ("/productos/nuevo", _producto, Product, "nombre", MAX_NOMBRE),
    ("/productos/nuevo", _producto, Product, "descripcion", MAX_DESCRIPCION_PRODUCTO),
    ("/servicios/nuevo", _servicio, Service, "titulo", MAX_TITULO_SERVICIO),
    ("/servicios/nuevo", _servicio, Service, "descripcion", MAX_DESCRIPCION_SERVICIO),
    ("/servicios/nuevo", _servicio, Service, "zona_cobertura", MAX_ZONA_COBERTURA),
])
def test_en_mysql_el_formulario_contesta_en_vez_de_morir(
    app_en_mysql, ruta, datos, modelo, campo, maximo
):
    """Los ocho campos, contra la base donde el bug era un 500.

    Sin la validacion esto es un DataError sin atrapar: 500 para el usuario y
    la sesion de SQLAlchemy rota. Con ella, el formulario vuelve con su error.
    """
    respuesta = app_en_mysql.client.post(
        ruta,
        data=datos(app_en_mysql.post.id, **{campo: "a" * (maximo + 1)}),
        follow_redirects=True,
    )

    assert respuesta.status_code == 200
    assert str(maximo) in respuesta.get_data(as_text=True)
    assert modelo.query.count() == 0
