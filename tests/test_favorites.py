"""Tests de favoritos: marcar/desmarcar emprendimientos y "Mis favoritos"."""

import re

from app.blog.modelo_favorito import Favorite
from app.blog.modelo_post import Categorias, Post


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
