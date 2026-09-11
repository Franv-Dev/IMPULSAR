"""Lo de la busqueda de personal que SQLite no puede probar.

Dos cosas, y las dos son las que la regla de H2 manda llevar a MySQL de verdad:

  - el COUNT agrupado de la bandeja, y al lado la contraprueba de que en este
    MySQL un GROUP BY que hereda un ORDER BY flojo REALMENTE muere con el error
    1055. Sin esa segunda mitad, la primera es un test que no puede fallar: la
    consulta real se arma de cero, no hereda ningun ORDER BY, y pasa con el
    .order_by(None) y sin el. SQLite acepta las dos formas calladito.
  - el incremento atomico del contador de vistas, que en SQLite corre siempre
    serializado y por eso nunca muestra la carrera.

El archivo arma su propia app y no usa las fixtures de conftest, por lo mismo
que app_en_mysql en test_largos.py: con aquellas la app se destruye DESPUES de
esta fixture, y el DROP DATABASE se queda esperando para siempre a una conexion
que todavia no se cerro.
"""

import os
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, text
from werkzeug.security import generate_password_hash

from app.blog.modelo_post import Post
from app.personal import consultas
from app.personal.modelo_busqueda import BusquedaPersonal, Modalidades
from app.personal.modelo_postulacion import Postulacion
from config import TestingConfig
from db import db as _db
from main import create_app
from models.user import Roles, User


def _servidor_mysql():
    """La URI del MySQL local SIN base, armada como la arma config.py."""
    return (
        f"mysql+pymysql://{os.getenv('DB_USER', '')}:{os.getenv('DB_PASSWORD', '')}"
        f"@{os.getenv('DB_HOST', 'localhost')}:{os.getenv('DB_PORT', '3306')}"
    )


@pytest.fixture
def personal_en_mysql():
    """Una busqueda con sus postulaciones, contra MySQL, en base descartable.

    Se saltea si no hay servidor, y tambien si falta ONLY_FULL_GROUP_BY: sin
    ese modo MySQL acepta el GROUP BY flojo igual que SQLite y el test no
    probaria nada, que es exactamente lo que hay que evitar aca.
    """
    try:
        motor = create_engine(_servidor_mysql())
        conexion = motor.connect()
    except Exception as error:  # servidor apagado, credenciales, driver
        pytest.skip(f"sin MySQL local: {error}")

    base = "impulsar_test_personal"
    with conexion:
        modo = conexion.execute(text("SELECT @@SESSION.sql_mode")).scalar() or ""
        if "ONLY_FULL_GROUP_BY" not in modo:
            motor.dispose()
            pytest.skip(
                f"MySQL sin ONLY_FULL_GROUP_BY, el test no probaria nada: {modo}"
            )
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
        dueña = User(
            username="tomy", email="tomy@test.com",
            password=generate_password_hash("secreta123"), rol=Roles.EMPRENDEDOR,
        )
        _db.session.add(dueña)
        _db.session.commit()
        post = Post(author=dueña.id, title="Panadería", body="Pan")
        _db.session.add(post)
        _db.session.commit()

        def crear_busqueda(puesto="Ayudante", activa=True):
            busqueda = BusquedaPersonal(
                post_id=post.id, puesto=puesto,
                modalidad=Modalidades.PRESENCIAL,
                descripcion="Cuatro horas por la mañana.", activa=activa,
            )
            _db.session.add(busqueda)
            _db.session.commit()
            return busqueda

        def postular(busqueda_id, nombre):
            persona = User(
                username=nombre, email=f"{nombre}@test.com",
                password=generate_password_hash("secreta123"),
            )
            _db.session.add(persona)
            _db.session.commit()
            _db.session.add(Postulacion(
                busqueda_id=busqueda_id, postulante_id=persona.id,
                nombre=nombre, contacto="2614445566",
                experiencia="Dos años.", disponibilidad="Mañanas",
            ))
            _db.session.commit()

        yield SimpleNamespace(
            app=app, db=_db, post=post,
            crear_busqueda=crear_busqueda, postular=postular,
        )

        _db.session.remove()
        motores = list(app.extensions["sqlalchemy"].engines.values())

    for motor_de_la_app in motores:
        motor_de_la_app.dispose()
    with motor.connect() as conexion:
        conexion.execute(text(f"DROP DATABASE IF EXISTS {base}"))
    motor.dispose()


def test_en_mysql_el_conteo_agrupado_no_explota(personal_en_mysql):
    """El COUNT por busqueda con ONLY_FULL_GROUP_BY prendido.

    Que hoy pase no prueba que el .order_by(None) sirva -- se comprobo sacandolo
    y sigue verde, porque esta consulta no hereda ningun ORDER BY. Lo que si
    prueba es que la agregacion es correcta contra el motor de produccion; de
    que el peligro existe se ocupa el test de abajo.
    """
    una = personal_en_mysql.crear_busqueda(puesto="Una", activa=False)
    otra = personal_en_mysql.crear_busqueda(puesto="Otra")
    personal_en_mysql.postular(una.id, "ana")
    personal_en_mysql.postular(una.id, "bruno")
    personal_en_mysql.postular(otra.id, "carla")

    conteo = consultas.conteo_de_postulaciones([una.id, otra.id])
    assert conteo == {una.id: 2, otra.id: 1}


def test_en_mysql_un_group_by_que_hereda_el_order_by_explota(personal_en_mysql):
    """La contraprueba del test de arriba, y la que lo hace valer algo.

    Sin esto, test_en_mysql_el_conteo_agrupado_no_explota es un test que no
    puede fallar: la consulta real se arma de cero y no hereda ningun ORDER BY,
    asi que pasa con .order_by(None) y sin el -- se comprobo sacandolo.

    Lo que se prueba aca es que el peligro existe y que este MySQL lo aplica:
    la MISMA agregacion, derivada de una consulta ordenada por una columna que
    no esta en el GROUP BY, muere con el error 1055. Si mañana alguien escribe
    la bandeja asi (listar ordenado y de paso contar), esto es lo que va a
    pasar en produccion y no en la suite en SQLite.
    """
    from sqlalchemy import func
    from sqlalchemy.exc import OperationalError

    busqueda = personal_en_mysql.crear_busqueda()
    personal_en_mysql.postular(busqueda.id, "ana")

    floja = (
        personal_en_mysql.db.session.query(
            Postulacion.busqueda_id, func.count(Postulacion.id)
        )
        .order_by(Postulacion.created_at)
        .group_by(Postulacion.busqueda_id)
    )
    with pytest.raises(OperationalError) as estallo:
        floja.all()
    assert "1055" in str(estallo.value)


def test_en_mysql_la_bandeja_responde(personal_en_mysql):
    """La pantalla entera y no solo la consulta suelta: el listado ordenado y
    el conteo agrupado salen juntos de la misma vista, que es donde alguien
    podria encadenarlos sin querer."""
    busqueda = personal_en_mysql.crear_busqueda()
    personal_en_mysql.postular(busqueda.id, "ana")

    cliente = personal_en_mysql.app.test_client()
    with cliente.session_transaction() as sesion:
        sesion["user_id"] = personal_en_mysql.post.author

    respuesta = cliente.get("/personal/postulantes")
    assert respuesta.status_code == 200
    assert "Ayudante" in respuesta.get_data(as_text=True)


def test_en_mysql_el_contador_de_vistas_suma_en_la_base(personal_en_mysql):
    """El +1 lo resuelve el motor, no Python.

    Se leen los dos incrementos con el identity map vaciado: si la suma se
    hiciera leyendo el valor en memoria, el segundo pisaria al primero y esto
    quedaria en 1.
    """
    busqueda_id = personal_en_mysql.crear_busqueda().id

    consultas.contar_vista_sin_postulacion(busqueda_id)
    consultas.contar_vista_sin_postulacion(busqueda_id)

    personal_en_mysql.db.session.expunge_all()
    fresca = BusquedaPersonal.query.get(busqueda_id)
    assert fresca.vistas_sin_postulacion == 2


def test_en_mysql_una_sola_busqueda_activa(personal_en_mysql):
    """El unique parcial tambien en MySQL: los NULL no chocan entre si, y por
    eso las cerradas se pueden acumular pero las activas no."""
    from sqlalchemy.exc import IntegrityError

    personal_en_mysql.crear_busqueda(puesto="La abierta")
    with pytest.raises(IntegrityError):
        personal_en_mysql.crear_busqueda(puesto="Otra abierta")
    personal_en_mysql.db.session.rollback()

    personal_en_mysql.crear_busqueda(puesto="Una cerrada", activa=False)
    personal_en_mysql.crear_busqueda(puesto="Otra cerrada", activa=False)
    assert BusquedaPersonal.query.filter_by(activa=False).count() == 2
