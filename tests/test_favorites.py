"""Tests de favoritos: marcar/desmarcar emprendimientos y "Mis favoritos"."""

import os
import re
from datetime import datetime
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, text
from werkzeug.security import generate_password_hash

from app.blog.modelo_favorito import Favorite
from app.blog.modelo_post import Categorias, Post
from config import TestingConfig
from db import db as _db
from main import create_app
from models.user import User


def _servidor_mysql():
    """La URI del MySQL local SIN base, armada como la arma config.py."""
    return (
        f"mysql+pymysql://{os.getenv('DB_USER', '')}:{os.getenv('DB_PASSWORD', '')}"
        f"@{os.getenv('DB_HOST', 'localhost')}:{os.getenv('DB_PORT', '3306')}"
    )


def _entorno(client, db, crear_usuario, crear_post, login):
    """Junta en un objeto lo que necesita un test para armar un escenario.

    Existe para que el mismo escenario se pueda correr con las fixtures de
    siempre (SQLite) o con las que arma app_en_mysql, sin duplicar el test.
    """
    return SimpleNamespace(
        client=client,
        db=db,
        crear_usuario=crear_usuario,
        crear_post=crear_post,
        login=login,
    )


@pytest.fixture
def app_en_mysql():
    """La app de testing, pero contra un MySQL de verdad.

    Se saltea el test si no hay servidor a mano: la suite corre en SQLite y el
    CI no levanta uno (ver .github/workflows/tests.yml).

    La base es DESCARTABLE y tiene nombre propio: se crea vacia y se borra al
    terminar, asi que correr los tests nunca toca la base de desarrollo.

    NO USA LAS FIXTURES DE conftest (app, client, crear_usuario...) y arma todo
    de nuevo, que es lo unico que da control del orden de limpieza. Con
    aquellas, la app se destruye DESPUES de esta fixture y el DROP DATABASE se
    queda esperando para siempre a una conexion que todavia no se cerro. Aca el
    orden es explicito: cerrar la sesion, soltar los motores, y recien
    entonces borrar la base.
    """
    try:
        motor = create_engine(_servidor_mysql())
        conexion = motor.connect()
    except Exception as error:  # servidor apagado, credenciales, driver
        pytest.skip(f"sin MySQL local: {error}")

    base = "impulsar_test_favoritos"
    with conexion:
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

        def crear_usuario(username):
            usuario = User(
                username=username,
                email=f"{username}@test.com",
                password=generate_password_hash("secreta123"),
            )
            _db.session.add(usuario)
            _db.session.commit()
            return usuario

        def crear_post(author_id, title):
            post = Post(author=author_id, title=title, body="Pan artesanal")
            _db.session.add(post)
            _db.session.commit()
            return post

        def login(user_id):
            with client.session_transaction() as sesion:
                sesion["user_id"] = user_id

        yield _entorno(client, _db, crear_usuario, crear_post, login)

        _db.session.remove()
        motores = list(app.extensions["sqlalchemy"].engines.values())

    for motor_de_la_app in motores:
        motor_de_la_app.dispose()
    with motor.connect() as conexion:
        conexion.execute(text(f"DROP DATABASE IF EXISTS {base}"))
    motor.dispose()


def test_marcar_como_favorito(client, db, crear_usuario, crear_post, login):
    usuario = crear_usuario(username="tomy")
    autor = crear_usuario(username="autor")
    post = crear_post(autor.id)

    login(usuario.id)
    client.post(f"/blog/{post.id}/favorito")

    favorito = Favorite.query.filter_by(user_id=usuario.id, post_id=post.id).first()
    assert favorito is not None


def test_marcar_dos_veces_lo_desmarca(client, db, crear_usuario, crear_post, login):
    """El boton es un toggle: la segunda vez que se aprieta, lo saca de favoritos."""
    usuario = crear_usuario(username="tomy")
    autor = crear_usuario(username="autor")
    post = crear_post(autor.id)

    login(usuario.id)
    client.post(f"/blog/{post.id}/favorito")
    client.post(f"/blog/{post.id}/favorito")

    assert Favorite.query.filter_by(user_id=usuario.id, post_id=post.id).count() == 0


def test_favoritos_requiere_login(client, crear_usuario, crear_post):
    autor = crear_usuario(username="autor")
    post = crear_post(autor.id)

    resp = client.post(f"/blog/{post.id}/favorito", follow_redirects=False)

    assert resp.status_code == 302
    assert "/auth/login" in resp.headers["Location"]


def test_mis_favoritos_lista_solo_los_propios(client, db, crear_usuario, crear_post, login):
    usuario = crear_usuario(username="tomy")
    otro = crear_usuario(username="otro")
    autor = crear_usuario(username="autor")
    favorito = crear_post(autor.id, title="Lo marqué yo")
    no_favorito = crear_post(autor.id, title="No lo marqué")

    db.session.add(Favorite(user_id=usuario.id, post_id=favorito.id))
    db.session.add(Favorite(user_id=otro.id, post_id=no_favorito.id))
    db.session.commit()

    login(usuario.id)
    html = client.get("/blog/favoritos").get_data(as_text=True)

    assert "Lo marqué yo" in html
    assert "No lo marqué" not in html


def test_dos_usuarios_pueden_marcar_el_mismo_post_sin_chocar(
    client, db, crear_usuario, crear_post, login
):
    uno = crear_usuario(username="uno")
    dos = crear_usuario(username="dos")
    autor = crear_usuario(username="autor")
    post = crear_post(autor.id)

    login(uno.id)
    client.post(f"/blog/{post.id}/favorito")
    login(dos.id)
    client.post(f"/blog/{post.id}/favorito")

    assert Favorite.query.filter_by(post_id=post.id).count() == 2


# --------------------------------------------- ON DELETE CASCADE (FK 1451)

def test_se_puede_eliminar_un_post_con_favoritos(client, db, crear_usuario, crear_post, login):
    """Antes del fix, esto fallaba con IntegrityError 1451 en MySQL: el FK
    de favorites.post_id era RESTRICT por default."""
    autor = crear_usuario(username="autor")
    cliente = crear_usuario(username="cliente")
    post = crear_post(autor.id)

    login(cliente.id)
    client.post(f"/blog/{post.id}/favorito")
    assert Favorite.query.filter_by(post_id=post.id).count() == 1

    login(autor.id)
    resp = client.post(f"/blog/delete/{post.id}", follow_redirects=False)

    assert resp.status_code == 302
    assert Post.query.get(post.id) is None
    assert Favorite.query.filter_by(post_id=post.id).count() == 0


# ---------------------------------------------- orden y filtros de "Mis favoritos"

def _marcar(client, post_id):
    """Marca un favorito por la ruta real, que es la que escribe Favorite.created."""
    client.post(f"/blog/{post_id}/favorito")


def _titulos_en(html):
    """Los titulos de las tarjetas, en el orden en que salen en la pagina."""
    return re.findall(r'<h3 class="card__title">\s*<a[^>]*>\s*(.*?)\s*</a>', html)


def test_ordena_por_cuando_se_marco_y_no_por_cuando_se_publico(
    client, db, crear_usuario, crear_post, login
):
    """El fix: la pantalla es la lista de marcas del usuario.

    Los dos posts se publican en orden A, B, pero se marcan al reves. Con el
    orden viejo (Post.created.desc()) arriba salia B porque se publico despues;
    lo que el usuario espera es A, que es lo ultimo que guardo.
    """
    usuario = crear_usuario(username="tomy")
    autor = crear_usuario(username="autor")
    a = crear_post(autor.id, title="Primero publicado")
    b = crear_post(autor.id, title="Segundo publicado")

    login(usuario.id)
    _marcar(client, b.id)
    _marcar(client, a.id)

    assert _titulos_en(client.get("/blog/favoritos").get_data(as_text=True)) == [
        "Primero publicado", "Segundo publicado",
    ]


def test_lo_ultimo_marcado_va_primero(client, db, crear_usuario, crear_post, login):
    """Marcar A, despues B, y B tiene que salir primero.

    B se PUBLICA antes que A a proposito. Publicandolos en orden alfabetico,
    el orden por Post.created y el orden por Favorite.created dan lo mismo y
    el test pasaria igual con el bug puesto; al revés, solo pasa si el ORDER
    BY es el de la marca.
    """
    usuario = crear_usuario(username="tomy")
    autor = crear_usuario(username="autor")
    b = crear_post(autor.id, title="Panaderia B")
    a = crear_post(autor.id, title="Panaderia A")

    login(usuario.id)
    _marcar(client, a.id)
    _marcar(client, b.id)

    assert _titulos_en(client.get("/blog/favoritos").get_data(as_text=True)) == [
        "Panaderia B", "Panaderia A",
    ]


def test_el_orden_por_nombre_ignora_las_mayusculas(
    client, db, crear_usuario, crear_post, login
):
    """A-Z de verdad, no el de SQLite.

    Un ORDER BY de texto sin lower() es sensible a mayusculas en SQLite y pone
    "Zapateria" antes que "alfajores"; con lower() el orden es el que promete
    la etiqueta, y ademas el mismo que daria MySQL.
    """
    usuario = crear_usuario(username="tomy")
    autor = crear_usuario(username="autor")
    login(usuario.id)
    for titulo in ("Zapateria central", "alfajores del sur", "Bicicleteria"):
        post = crear_post(autor.id, title=titulo)
        _marcar(client, post.id)

    html = client.get("/blog/favoritos?orden=nombre").get_data(as_text=True)

    assert _titulos_en(html) == [
        "alfajores del sur", "Bicicleteria", "Zapateria central",
    ]


def test_un_orden_inventado_cae_en_el_default(client, db, crear_usuario, crear_post, login):
    """El parametro viaja en la URL y se escribe a mano. Un valor que no existe
    no puede vaciar la pantalla ni tirar un error: es una preferencia de como
    mirar lo mismo, asi que cae al default."""
    usuario = crear_usuario(username="tomy")
    autor = crear_usuario(username="autor")
    # Publicados al reves de como se marcan, por lo mismo que en el test de
    # arriba: si no, el default no se distingue del orden viejo.
    b = crear_post(autor.id, title="Panaderia B")
    a = crear_post(autor.id, title="Panaderia A")

    login(usuario.id)
    _marcar(client, a.id)
    _marcar(client, b.id)

    html = client.get("/blog/favoritos?orden=lo-que-sea").get_data(as_text=True)

    assert _titulos_en(html) == ["Panaderia B", "Panaderia A"]


def test_filtra_por_rubro(client, db, crear_usuario, crear_post, login):
    usuario = crear_usuario(username="tomy")
    autor = crear_usuario(username="autor")
    alimento = crear_post(autor.id, title="Panaderia", category=Categorias.ALIMENTOS)
    tecno = crear_post(autor.id, title="Reparacion de PCs", category=Categorias.TECNOLOGIA)

    login(usuario.id)
    _marcar(client, alimento.id)
    _marcar(client, tecno.id)

    html = client.get(f"/blog/favoritos?category={Categorias.ALIMENTOS}").get_data(as_text=True)

    assert "Panaderia" in html
    assert "Reparacion de PCs" not in html


def test_el_filtro_de_rubro_no_toca_los_favoritos_de_otro(
    client, db, crear_usuario, crear_post, login
):
    """Filtrar acota lo propio, no abre lo ajeno."""
    usuario = crear_usuario(username="tomy")
    otro = crear_usuario(username="otro")
    autor = crear_usuario(username="autor")
    mio = crear_post(autor.id, title="Lo marque yo", category=Categorias.ALIMENTOS)
    ajeno = crear_post(autor.id, title="Lo marco el otro", category=Categorias.ALIMENTOS)
    db.session.add_all([
        Favorite(user_id=usuario.id, post_id=mio.id),
        Favorite(user_id=otro.id, post_id=ajeno.id),
    ])
    db.session.commit()

    login(usuario.id)
    html = client.get(f"/blog/favoritos?category={Categorias.ALIMENTOS}").get_data(as_text=True)

    assert "Lo marque yo" in html
    assert "Lo marco el otro" not in html


def test_un_rubro_inventado_no_filtra_nada(client, db, crear_usuario, crear_post, login):
    """Mismo trato que en Explorar: la categoria que no existe se ignora en vez
    de vaciar la pantalla."""
    usuario = crear_usuario(username="tomy")
    autor = crear_usuario(username="autor")
    post = crear_post(autor.id, title="Panaderia", category=Categorias.ALIMENTOS)

    login(usuario.id)
    _marcar(client, post.id)

    assert "Panaderia" in client.get(
        "/blog/favoritos?category=no-existe"
    ).get_data(as_text=True)


def test_el_rubro_y_el_orden_se_combinan(client, db, crear_usuario, crear_post, login):
    """Los dos filtros son independientes y tienen que poder convivir: el rubro
    acota y el orden ordena lo que quedo."""
    usuario = crear_usuario(username="tomy")
    autor = crear_usuario(username="autor")
    zapateria = crear_post(autor.id, title="Zapateria", category=Categorias.INDUMENTARIA)
    almacen = crear_post(autor.id, title="Almacen", category=Categorias.ALIMENTOS)
    bodega = crear_post(autor.id, title="Bodega", category=Categorias.ALIMENTOS)

    login(usuario.id)
    # Se marcan al reves del alfabeto para que el orden por nombre no coincida
    # por casualidad con el orden por fecha.
    _marcar(client, zapateria.id)
    _marcar(client, bodega.id)
    _marcar(client, almacen.id)

    html = client.get(
        f"/blog/favoritos?category={Categorias.ALIMENTOS}&orden=nombre"
    ).get_data(as_text=True)

    assert _titulos_en(html) == ["Almacen", "Bodega"]
    assert "Zapateria" not in html


def test_los_selects_vuelven_marcados_con_lo_elegido(
    client, db, crear_usuario, crear_post, login
):
    """Si la pantalla no repinta lo elegido, el usuario no sabe que esta viendo
    filtrado."""
    usuario = crear_usuario(username="tomy")
    autor = crear_usuario(username="autor")
    post = crear_post(autor.id, title="Panaderia", category=Categorias.ALIMENTOS)

    login(usuario.id)
    _marcar(client, post.id)

    html = client.get(
        f"/blog/favoritos?category={Categorias.ALIMENTOS}&orden=nombre"
    ).get_data(as_text=True)

    assert re.search(rf'value="{Categorias.ALIMENTOS}"[^>]*selected', html)
    assert re.search(r'value="nombre"[^>]*selected', html)


def test_sin_orden_en_la_url_queda_marcado_el_default(
    client, db, crear_usuario, crear_post, login
):
    usuario = crear_usuario(username="tomy")
    autor = crear_usuario(username="autor")
    post = crear_post(autor.id, title="Panaderia")

    login(usuario.id)
    _marcar(client, post.id)

    html = client.get("/blog/favoritos").get_data(as_text=True)

    assert re.search(r'value="reciente"[^>]*selected', html)


def test_el_rubro_sobrevive_al_cambio_de_pagina(
    app, client, db, crear_usuario, crear_post, login
):
    """La paginacion arrastra la querystring (ver partials/_paginacion.html).
    Si el filtro se perdiera, la pagina 2 mostraria cosas de otros rubros."""
    usuario = crear_usuario(username="tomy")
    autor = crear_usuario(username="autor")
    por_pagina = app.config["POSTS_POR_PAGINA"]

    login(usuario.id)
    for numero in range(por_pagina + 2):
        post = crear_post(
            autor.id, title=f"Alimento {numero}", category=Categorias.ALIMENTOS
        )
        _marcar(client, post.id)
    otro_rubro = crear_post(
        autor.id, title="Tecnologia suelta", category=Categorias.TECNOLOGIA
    )
    _marcar(client, otro_rubro.id)

    html = client.get(
        f"/blog/favoritos?category={Categorias.ALIMENTOS}&page=2"
    ).get_data(as_text=True)

    assert "Tecnologia suelta" not in html
    assert len(_titulos_en(html)) == 2


def test_el_vacio_por_filtro_ofrece_sacar_el_filtro(
    client, db, crear_usuario, crear_post, login
):
    """Tener favoritos pero ninguno de ese rubro NO es lo mismo que no tener
    ninguno: la salida de cada situacion es distinta."""
    usuario = crear_usuario(username="tomy")
    autor = crear_usuario(username="autor")
    post = crear_post(autor.id, title="Panaderia", category=Categorias.ALIMENTOS)

    login(usuario.id)
    _marcar(client, post.id)

    html = client.get(
        f"/blog/favoritos?category={Categorias.TECNOLOGIA}"
    ).get_data(as_text=True)

    assert "No tenés favoritos en ese rubro" in html
    assert "Todavía no marcaste ningún emprendimiento" not in html


# ------------------------------------------- el desempate del orden (empate de fecha)
#
# Los dos tests de abajo son el mismo caso visto en los dos motores: cinco
# favoritos marcados con la misma fecha. El de MySQL es el que reproduce el
# bug tal cual pasa en produccion (la columna es DATETIME(0) y empata sola,
# asi que basta con marcar cinco seguidos), pero necesita un servidor y en el
# CI no hay, asi que ahi se saltea. El de SQLite arma el empate a mano para
# que la regresion igual quede cubierta en cada push.

def _cinco_favoritos_empatados(entorno):
    """Marca A..E y les deja a los cinco la MISMA fecha. Devuelve los titulos."""
    usuario = entorno.crear_usuario(username="tomy")
    autor = entorno.crear_usuario(username="autor")
    titulos = ["Favorito A", "Favorito B", "Favorito C", "Favorito D", "Favorito E"]
    posts = [entorno.crear_post(autor.id, title=titulo) for titulo in titulos]

    entorno.login(usuario.id)
    for post in posts:
        _marcar(entorno.client, post.id)

    # Distinto microsegundo dentro del MISMO segundo, que es lo que escribe la
    # ruta cuando alguien marca varios seguidos. En MySQL los cinco caen en el
    # mismo segundo y quedan empatados; en SQLite hay que empatarlos a mano (lo
    # hace el test de abajo) porque guarda el microsegundo entero.
    #
    # Todos por debajo del medio segundo a proposito: MySQL no trunca el
    # DATETIME(0), lo REDONDEA, asi que un .5 se guardaria como el segundo
    # siguiente y romperia el empate que el test necesita.
    base = datetime(2026, 9, 3, 12, 0, 0)
    for i, favorito in enumerate(Favorite.query.order_by(Favorite.id).all()):
        favorito.created = base.replace(microsecond=50000 * (i + 1))
    entorno.db.session.commit()
    return titulos


def test_en_mysql_los_favoritos_del_mismo_segundo_salen_del_ultimo_al_primero(
    app_en_mysql,
):
    """El hallazgo: en produccion la fecha del favorito no desempata sola.

    Es DATETIME(0), asi que marcar cinco emprendimientos seguidos (un segundo
    alcanza de sobra) deja cinco filas con la MISMA fecha, y sin desempate
    MySQL las devuelve en el orden que quiere: en la practica, el de la clave
    primaria, o sea del primero marcado al ultimo, justo al reves de lo que
    promete "Recientes". Ademas es inestable entre consultas, y eso paginado
    se ve como una tarjeta repetida en dos paginas.

    Corre contra un MySQL de verdad y no con el dialecto compilado a mano
    (como test_turnos) porque lo que se prueba no es el SQL que se emite sino
    el resultado que devuelve el motor.
    """
    titulos = _cinco_favoritos_empatados(app_en_mysql)

    # Que el empate exista de verdad, y por la razon que dice el docstring: si
    # algun dia la columna pasa a DATETIME(6) esto avisa que el test dejo de
    # probar lo que cree.
    fechas = {f.created for f in Favorite.query.all()}
    assert len(fechas) == 1, f"MySQL no redondeo al segundo: {fechas}"

    html = app_en_mysql.client.get("/blog/favoritos").get_data(as_text=True)
    assert _titulos_en(html) == list(reversed(titulos))


def test_los_favoritos_con_la_misma_fecha_salen_del_ultimo_al_primero(
    client, db, crear_usuario, crear_post, login
):
    """El mismo caso que el de MySQL, con el empate armado a mano.

    Existe para que el CI, que corre en SQLite y no tiene servidor MySQL,
    tambien frene la regresion. Sin el desempate SQLite devuelve las filas por
    rowid, o sea de la primera marcada a la ultima, y el assert falla.
    """
    titulos = _cinco_favoritos_empatados(
        _entorno(client, db, crear_usuario, crear_post, login)
    )

    misma = datetime(2026, 9, 3, 12, 0, 0)
    for favorito in Favorite.query.all():
        favorito.created = misma
    db.session.commit()

    html = client.get("/blog/favoritos").get_data(as_text=True)
    assert _titulos_en(html) == list(reversed(titulos))
