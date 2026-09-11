"""Tests del conteo por mes de la cartelera (B2 de la auditoria del 10/9).

El rotulo de cada mes se alimentaba de `agrupar_por_mes(paginacion.items)`, o
sea de la PAGINA. Con un mes partido entre dos paginas el mes aparecia dos
veces y ninguno de los dos numeros era el suyo: la evidencia de la auditoria,
con 14 eventos en octubre y POSTS_POR_PAGINA=9, era «octubre 2026 · 6 eventos»
en la pagina 1 y «octubre 2026 · 7 eventos» en la 2, siendo 13 el real.

La lista de cada grupo sigue siendo la de la pagina (un mes partido en dos se
recorre en dos pantallas, que es lo mismo que pasa con cualquier corte por
fecha); lo que cambia es el numero de al lado.

AL FINAL HAY UN TEST CONTRA MySQL REAL, y no es decorativo: el arreglo de B2 es
un COUNT agrupado, y un GROUP BY con un ORDER BY que no esta en el es un error
en MySQL 8 (ONLY_FULL_GROUP_BY viene prendido de fabrica) que SQLite acepta sin
decir nada. O sea que el arreglo de B2 podia ser otro 500 que solo aparece en
produccion. Sin ese test, sacar el order_by(None) de total_por_mes deja la
suite entera en verde.
"""

import os
import re
from datetime import date
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, text
from werkzeug.security import generate_password_hash

from app.blog.modelo_post import Post
from config import TestingConfig
from db import db as _db
from main import create_app
from models.event import Event
from models.user import Roles, User
from services.eventos import agrupar_por_mes, proximos, total_por_mes


@pytest.fixture
def cartelera(client, db, crear_usuario, crear_post):
    """Un emprendimiento al que colgarle eventos, y una fabrica de eventos."""
    usuario = crear_usuario(username="tomy", rol=Roles.EMPRENDEDOR)
    post = crear_post(usuario.id)

    def _evento(fecha, titulo="Feria"):
        evento = Event(post_id=post.id, titulo=titulo, fecha=fecha, tipo="feria")
        db.session.add(evento)
        db.session.commit()
        return evento

    return _evento


def _meses_en_pantalla(html):
    """[('octubre 2026', 13), ...] tal como los muestra la cartelera."""
    encabezados = re.findall(
        r'cartelera__mes-titulo">\s*(.*?)\s*</h3>.*?'
        r'cartelera__mes-total">\s*(\d+) evento',
        html,
        re.DOTALL,
    )
    return [(nombre, int(total)) for nombre, total in encabezados]


# ---------------------------------------------------------------- la funcion

def test_total_por_mes_cuenta_el_mes_entero(client, db, cartelera):
    for dia in range(1, 15):
        cartelera(date(2026, 10, dia))
    cartelera(date(2026, 11, 3))

    totales = total_por_mes(Event.query)

    assert totales[(2026, 10)] == 14
    assert totales[(2026, 11)] == 1


def test_total_por_mes_respeta_el_filtro_que_le_llega(client, db, cartelera):
    """Cuenta sobre la consulta filtrada, no sobre la tabla entera."""
    for dia in range(1, 6):
        cartelera(date(2026, 10, dia))
    cartelera(date(2026, 10, 20), titulo="Otra")

    totales = total_por_mes(Event.query.filter(Event.titulo == "Otra"))

    assert totales == {(2026, 10): 1}


def test_agrupar_por_mes_sin_totales_cuenta_la_lista(client, db, cartelera):
    """El caso de una lista ya completa: el total es su largo."""
    uno = cartelera(date(2026, 10, 1))
    dos = cartelera(date(2026, 10, 2))

    grupos = agrupar_por_mes([uno, dos])

    assert grupos[0]["total"] == 2


def test_agrupar_por_mes_usa_el_total_que_le_pasan(client, db, cartelera):
    """Y no el largo del recorte, que es justamente el bug."""
    uno = cartelera(date(2026, 10, 1))

    grupos = agrupar_por_mes([uno], {(2026, 10): 13})

    assert grupos[0]["total"] == 13
    assert len(grupos[0]["eventos"]) == 1


def test_un_mes_que_el_conteo_no_trajo_cae_en_el_largo(client, db, cartelera):
    uno = cartelera(date(2026, 10, 1))

    grupos = agrupar_por_mes([uno], {})

    assert grupos[0]["total"] == 1


# ------------------------------------------------------- la pantalla completa

def test_un_mes_partido_muestra_su_total_en_las_dos_paginas(client, db, cartelera):
    """El escenario exacto de la auditoria: 14 en octubre, 9 por pagina.

    Antes decia 9 en la primera y 5 en la segunda (o 6 y 7 con septiembre
    adelante). Ahora las dos dicen 14, que es lo que octubre tiene.
    """
    for dia in range(1, 15):
        cartelera(date(2026, 10, dia))

    pagina1 = _meses_en_pantalla(client.get("/eventos/").get_data(as_text=True))
    pagina2 = _meses_en_pantalla(
        client.get("/eventos/?page=2").get_data(as_text=True)
    )

    assert pagina1 == [("octubre 2026", 14)]
    assert pagina2 == [("octubre 2026", 14)]


def test_el_numero_del_mes_no_es_el_de_la_pagina(client, db, cartelera):
    """Con tres meses repartidos, cada rotulo dice lo suyo y no su recorte."""
    for dia in range(1, 4):
        cartelera(date(2026, 9, dia + 20))
    for dia in range(1, 14):
        cartelera(date(2026, 10, dia))
    for dia in range(1, 3):
        cartelera(date(2026, 11, dia))

    pagina1 = dict(_meses_en_pantalla(client.get("/eventos/").get_data(as_text=True)))
    pagina2 = dict(
        _meses_en_pantalla(client.get("/eventos/?page=2").get_data(as_text=True))
    )

    # Octubre aparece en las dos paginas y dice 13 en las dos.
    assert pagina1["septiembre 2026"] == 3
    assert pagina1["octubre 2026"] == 13
    assert pagina2["octubre 2026"] == 13
    assert pagina2["noviembre 2026"] == 2


def test_el_conteo_sigue_al_filtro_de_la_cartelera(client, db, cartelera):
    """Filtrando por tipo, el rotulo cuenta los del filtro y no todos."""
    for dia in range(1, 6):
        cartelera(date(2026, 10, dia))
    taller = Event(
        post_id=cartelera(date(2026, 10, 20)).post_id,
        titulo="Taller de cerámica",
        fecha=date(2026, 10, 21),
        tipo="taller",
    )
    db.session.add(taller)
    db.session.commit()

    html = client.get("/eventos/?tipo=taller").get_data(as_text=True)

    assert _meses_en_pantalla(html) == [("octubre 2026", 1)]


def test_un_solo_evento_dice_evento_en_singular(client, db, cartelera):
    cartelera(date(2026, 10, 1))

    html = client.get("/eventos/").get_data(as_text=True)

    assert "1 evento" in html
    assert "1 eventos" not in html


# ------------------------------------------------------ contra MySQL de verdad
#
# Lo unico que SQLite no puede probar de esta pantalla, y es justo donde el
# arreglo se puede romper: el COUNT agrupado.


def _servidor_mysql():
    """La URI del MySQL local SIN base, armada como la arma config.py."""
    return (
        f"mysql+pymysql://{os.getenv('DB_USER', '')}:{os.getenv('DB_PASSWORD', '')}"
        f"@{os.getenv('DB_HOST', 'localhost')}:{os.getenv('DB_PORT', '3306')}"
    )


@pytest.fixture
def cartelera_en_mysql():
    """La cartelera contra un MySQL de verdad, en base descartable.

    Arma su propia app y no usa las fixtures de conftest, por lo mismo que
    app_en_mysql en test_largos.py y en test_favorites.py: con aquellas, la app
    se destruye DESPUES de esta fixture y el DROP DATABASE se queda esperando
    para siempre a una conexion que todavia no se cerro.

    Se saltea si no hay servidor, y tambien si falta ONLY_FULL_GROUP_BY: sin
    ese modo MySQL acepta el GROUP BY flojo igual que SQLite y el test no
    probaria nada, que es exactamente lo que hay que evitar aca.
    """
    try:
        motor = create_engine(_servidor_mysql())
        conexion = motor.connect()
    except Exception as error:  # servidor apagado, credenciales, driver
        pytest.skip(f"sin MySQL local: {error}")

    base = "impulsar_test_cartelera"
    with conexion:
        modo = conexion.execute(text("SELECT @@SESSION.sql_mode")).scalar() or ""
        if "ONLY_FULL_GROUP_BY" not in modo:
            motor.dispose()
            pytest.skip(f"MySQL sin ONLY_FULL_GROUP_BY, el test no probaria nada: {modo}")
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
        usuario = User(
            username="tomy",
            email="tomy@test.com",
            password=generate_password_hash("secreta123"),
            rol=Roles.EMPRENDEDOR,
        )
        _db.session.add(usuario)
        _db.session.commit()
        post = Post(author=usuario.id, title="Huerta", body="Verduras")
        _db.session.add(post)
        _db.session.commit()

        def agregar(fecha):
            _db.session.add(
                Event(post_id=post.id, titulo="Feria", fecha=fecha, tipo="feria")
            )
            _db.session.commit()

        yield SimpleNamespace(app=app, db=_db, post=post, agregar=agregar)

        _db.session.remove()
        motores = list(app.extensions["sqlalchemy"].engines.values())

    for motor_de_la_app in motores:
        motor_de_la_app.dispose()
    with motor.connect() as conexion:
        conexion.execute(text(f"DROP DATABASE IF EXISTS {base}"))
    motor.dispose()


def test_en_mysql_el_conteo_por_mes_no_explota(cartelera_en_mysql):
    """El COUNT agrupado corriendo en la base donde el GROUP BY es estricto.

    Sobre la consulta REAL de la vista, que llega ordenada por fecha, hora e id
    (ver proximos). Esas tres columnas no estan en el GROUP BY: sin el
    order_by(None) de total_por_mes, MySQL 8 corta con un OperationalError 1055
    ("Expression #1 of ORDER BY clause is not in GROUP BY clause") y la
    cartelera entera es un 500. SQLite lo acepta, asi que este es el unico
    lugar de la suite donde ese fallo existe.
    """
    for dia in range(1, 15):
        cartelera_en_mysql.agregar(date(2026, 10, dia))
    cartelera_en_mysql.agregar(date(2026, 11, 3))

    consulta = proximos(Event.query, date(2026, 9, 10))
    totales = total_por_mes(consulta)

    assert totales == {(2026, 10): 14, (2026, 11): 1}


def test_en_mysql_la_cartelera_responde_y_muestra_el_total(cartelera_en_mysql):
    """La pantalla entera, no solo la funcion: es la que devolvia el 500."""
    for dia in range(1, 15):
        cartelera_en_mysql.agregar(date(2026, 10, dia))

    cliente = cartelera_en_mysql.app.test_client()
    respuesta = cliente.get("/eventos/")

    assert respuesta.status_code == 200
    assert _meses_en_pantalla(respuesta.get_data(as_text=True)) == [
        ("octubre 2026", 14)
    ]
