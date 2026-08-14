"""Tests de favoritos: marcar/desmarcar emprendimientos y "Mis favoritos"."""

from models.favorite import Favorite


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
