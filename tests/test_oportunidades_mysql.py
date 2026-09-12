"""Lo de las oportunidades que SQLite no puede probar.

Cuatro cosas, y las cuatro son diferencias reales entre el motor de la suite y
el de produccion:

  - el COUNT agrupado del listado, y al lado la contraprueba de que en este
    MySQL un GROUP BY que hereda un ORDER BY flojo REALMENTE muere con el error
    1055. Sin esa segunda mitad, la primera es un test que no puede fallar: la
    consulta real se arma de cero, no hereda ningun ORDER BY, y pasa con el
    .order_by(None) y sin el. SQLite acepta las dos formas calladito. Es la
    regla que quedo anotada despues de H2.
  - el empate de DATETIME(0): en MySQL la columna no guarda microsegundos, asi
    que dos propuestas cargadas en el mismo segundo tienen la MISMA fecha y el
    ORDER BY por created_at solo no las desempata. En SQLite no se ve nunca.
  - el unique parcial de la propuesta aceptada, con NULL de verdad.
  - que una violacion de CHECK en MySQL es OperationalError y no
    IntegrityError, que es lo que haria que un `except IntegrityError` no la
    atrape en produccion.

El archivo arma su propia app y no usa las fixtures de conftest, por lo mismo
que app_en_mysql en test_largos.py y personal_en_mysql en test_personal_mysql.py:
con aquellas la app se destruye DESPUES de esta fixture, y el DROP DATABASE se
queda esperando para siempre a una conexion que todavia no se cerro.
"""

import os
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, func, text
from sqlalchemy.exc import IntegrityError, OperationalError
from werkzeug.security import generate_password_hash

from app.blog.modelo_post import Post
from app.oportunidades import consultas
from app.oportunidades.modelo_oportunidad import EstadosOportunidad, Oportunidad
from app.oportunidades.modelo_propuesta import Propuesta
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
def oportunidades_en_mysql():
    """Una oportunidad con sus propuestas, contra MySQL, en base descartable.

    Se saltea si no hay servidor, y tambien si falta ONLY_FULL_GROUP_BY: sin
    ese modo MySQL acepta el GROUP BY flojo igual que SQLite y el test no
    probaria nada, que es exactamente lo que hay que evitar aca.
    """
    try:
        motor = create_engine(_servidor_mysql())
        conexion = motor.connect()
    except Exception as error:  # servidor apagado, credenciales, driver
        pytest.skip(f"sin MySQL local: {error}")

    base = "impulsar_test_oportunidades"
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
        autora = User(
            username="clienta", email="clienta@test.com",
            password=generate_password_hash("secreta123"),
        )
        emprendedor = User(
            username="disenio", email="disenio@test.com",
            password=generate_password_hash("secreta123"), rol=Roles.EMPRENDEDOR,
        )
        _db.session.add_all([autora, emprendedor])
        _db.session.commit()
        post = Post(author=emprendedor.id, title="Estudio de diseño", body="Diseño")
        _db.session.add(post)
        _db.session.commit()

        def crear_oportunidad(titulo="Necesito un logo", **kwargs):
            oportunidad = Oportunidad(
                autor_id=autora.id, titulo=titulo,
                descripcion="Tengo el nombre y los colores.", **kwargs,
            )
            _db.session.add(oportunidad)
            _db.session.commit()
            return oportunidad

        def proponer(oportunidad_id, precio="25000", plazo_dias=7, post_id=None):
            propuesta = Propuesta(
                oportunidad_id=oportunidad_id, post_id=post_id or post.id,
                precio=precio, plazo_dias=plazo_dias,
                mensaje="Te mando tres bocetos.",
            )
            _db.session.add(propuesta)
            _db.session.commit()
            return propuesta

        yield SimpleNamespace(
            app=app, db=_db, post=post, autora=autora, emprendedor=emprendedor,
            crear_oportunidad=crear_oportunidad, proponer=proponer,
        )

        _db.session.remove()
        motores = list(app.extensions["sqlalchemy"].engines.values())

    for motor_de_la_app in motores:
        motor_de_la_app.dispose()
    with motor.connect() as conexion:
        conexion.execute(text(f"DROP DATABASE IF EXISTS {base}"))
    motor.dispose()


def test_en_mysql_el_conteo_agrupado_no_explota(oportunidades_en_mysql):
    """El COUNT por oportunidad con ONLY_FULL_GROUP_BY prendido.

    Que hoy pase no prueba que el .order_by(None) sirva: esta consulta se arma
    de cero y no hereda ningun ORDER BY, asi que pasaria igual sin el. Lo que
    si prueba es que la agregacion es correcta contra el motor de produccion;
    de que el peligro existe se ocupa el test de abajo.
    """
    una = oportunidades_en_mysql.crear_oportunidad(titulo="Un logo")
    otra = oportunidades_en_mysql.crear_oportunidad(titulo="Un sitio")
    oportunidades_en_mysql.proponer(una.id)
    oportunidades_en_mysql.proponer(una.id, precio="20000")
    oportunidades_en_mysql.proponer(otra.id)

    conteo = consultas.conteo_de_propuestas([una.id, otra.id])
    assert conteo == {una.id: 2, otra.id: 1}


def test_en_mysql_un_group_by_que_hereda_el_order_by_explota(oportunidades_en_mysql):
    """La contraprueba del test de arriba, y la que lo hace valer algo.

    Se prueba que el peligro existe y que este MySQL lo aplica: la MISMA
    agregacion, derivada de una consulta ordenada por una columna que no esta
    en el GROUP BY ni dentro de una agregacion, muere con el error 1055. Si
    mañana alguien escribe el listado asi (listar ordenado y de paso contar),
    esto es lo que va a pasar en produccion y no en la suite en SQLite.
    """
    oportunidad = oportunidades_en_mysql.crear_oportunidad()
    oportunidades_en_mysql.proponer(oportunidad.id)

    floja = (
        oportunidades_en_mysql.db.session.query(
            Propuesta.oportunidad_id, func.count(Propuesta.id)
        )
        .order_by(Propuesta.created_at)
        .group_by(Propuesta.oportunidad_id)
    )
    with pytest.raises(OperationalError) as estallo:
        floja.all()
    assert "1055" in str(estallo.value)


def test_en_mysql_dos_propuestas_del_mismo_segundo_salen_en_orden_estable(
    oportunidades_en_mysql,
):
    """El empate de DATETIME(0), que SQLite tapa.

    En MySQL created_at no guarda microsegundos, asi que dos propuestas
    cargadas seguidas tienen literalmente la misma fecha y un ORDER BY por
    created_at solo deja el orden a criterio del motor. El id es el que
    desempata, y de eso depende cual propuesta se muestra como "la ultima" de
    cada emprendimiento.
    """
    oportunidad = oportunidades_en_mysql.crear_oportunidad()
    primera = oportunidades_en_mysql.proponer(oportunidad.id, precio="30000")
    segunda = oportunidades_en_mysql.proponer(oportunidad.id, precio="24000")

    # La premisa del test: si MySQL guardara microsegundos, esto no empataria y
    # el test no estaria probando lo que dice.
    assert primera.created_at.microsecond == 0
    assert segunda.created_at.microsecond == 0
    assert primera.created_at == segunda.created_at

    # Los ids se guardan ANTES de vaciar el identity map: despues las
    # instancias quedan desprendidas de la sesion y leerles un atributo
    # dispara un refresh que ya no tiene con que hacerse.
    oportunidad_id, primera_id, segunda_id = oportunidad.id, primera.id, segunda.id
    oportunidades_en_mysql.db.session.expunge_all()
    grupos = consultas.propuestas_de(oportunidad_id)

    assert len(grupos) == 1
    assert grupos[0]["ultima"].id == segunda_id
    assert [p.id for p in grupos[0]["anteriores"]] == [primera_id]


def test_en_mysql_una_sola_propuesta_aceptada(oportunidades_en_mysql):
    """El unique parcial tambien en MySQL: los NULL no chocan entre si, y por
    eso las no aceptadas se pueden acumular pero la aceptada es una sola."""
    oportunidad = oportunidades_en_mysql.crear_oportunidad()
    primera = oportunidades_en_mysql.proponer(oportunidad.id)
    segunda = oportunidades_en_mysql.proponer(oportunidad.id, precio="20000")

    primera.aceptada = True
    oportunidades_en_mysql.db.session.commit()

    segunda.aceptada = True
    with pytest.raises(IntegrityError):
        oportunidades_en_mysql.db.session.commit()
    oportunidades_en_mysql.db.session.rollback()

    # Y las no aceptadas siguen pudiendo ser todas las que hagan falta.
    oportunidades_en_mysql.proponer(oportunidad.id, precio="18000")
    assert Propuesta.query.filter_by(aceptada=False).count() == 2


def test_en_mysql_un_check_violado_es_operational_y_no_integrity(
    oportunidades_en_mysql,
):
    """En MySQL un CHECK violado llega como OperationalError.

    No es un detalle de tipos: un `except IntegrityError` alrededor de un
    INSERT no lo atrapa en produccion aunque en SQLite (donde SI es
    IntegrityError) parezca que si. Por eso el plazo y el precio se validan en
    el formulario y el CHECK es solo la red de abajo -- si el codigo dependiera
    de atrapar el choque, el usuario veria un 500.
    """
    oportunidad = oportunidades_en_mysql.crear_oportunidad()

    with pytest.raises(OperationalError):
        oportunidades_en_mysql.proponer(oportunidad.id, plazo_dias=0)
    oportunidades_en_mysql.db.session.rollback()


def test_en_mysql_el_listado_y_el_historial_responden(oportunidades_en_mysql):
    """Las pantallas enteras y no solo las consultas sueltas: el listado
    ordenado y el conteo agrupado salen juntos de la misma vista, que es donde
    alguien podria encadenarlos sin querer."""
    oportunidad = oportunidades_en_mysql.crear_oportunidad(titulo="Un logo")
    oportunidades_en_mysql.proponer(oportunidad.id)
    oportunidades_en_mysql.crear_oportunidad(
        titulo="Ya terminada", estado=EstadosOportunidad.FINALIZADA,
    )

    cliente = oportunidades_en_mysql.app.test_client()
    publico = cliente.get("/oportunidades/")
    assert publico.status_code == 200
    assert "Un logo" in publico.get_data(as_text=True)
    assert "Ya terminada" not in publico.get_data(as_text=True)

    with cliente.session_transaction() as sesion:
        sesion["user_id"] = oportunidades_en_mysql.autora.id
    historial = cliente.get("/oportunidades/mias")
    assert historial.status_code == 200
    assert "Ya terminada" in historial.get_data(as_text=True)
