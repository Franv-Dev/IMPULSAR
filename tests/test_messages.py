"""Tests del chat simple entre cliente y emprendedor."""

from models.message import Message
from app.blog.modelo_post import Post
from app.blog.modelo_resenia import Review


def test_el_cliente_puede_iniciar_una_conversacion(client, db, crear_usuario, crear_post, login):
    autor = crear_usuario(username="autor")
    cliente = crear_usuario(username="cliente")
    post = crear_post(autor.id)

    login(cliente.id)
    resp = client.post(
        f"/mensajes/{post.id}/{cliente.id}",
        data={"body": "Hola, ¿tenés stock?"},
        follow_redirects=False,
    )

    assert resp.status_code == 302
    mensaje = Message.query.filter_by(post_id=post.id, client_id=cliente.id).first()
    assert mensaje.body == "Hola, ¿tenés stock?"
    assert mensaje.sender_id == cliente.id


def test_el_dueño_puede_responder_en_la_conversacion(client, db, crear_usuario, crear_post, login):
    autor = crear_usuario(username="autor")
    cliente = crear_usuario(username="cliente")
    post = crear_post(autor.id)
    db.session.add(Message(post_id=post.id, client_id=cliente.id, sender_id=cliente.id, body="Hola"))
    db.session.commit()

    login(autor.id)
    client.post(f"/mensajes/{post.id}/{cliente.id}", data={"body": "Sí, tenemos stock"})

    respuesta = (
        Message.query
        .filter_by(post_id=post.id, client_id=cliente.id, sender_id=autor.id)
        .first()
    )
    assert respuesta.body == "Sí, tenemos stock"


def test_un_tercero_no_puede_ver_la_conversacion(client, db, crear_usuario, crear_post, login):
    autor = crear_usuario(username="autor")
    cliente = crear_usuario(username="cliente")
    intruso = crear_usuario(username="intruso")
    post = crear_post(autor.id)
    db.session.add(Message(post_id=post.id, client_id=cliente.id, sender_id=cliente.id, body="Hola"))
    db.session.commit()

    login(intruso.id)
    resp = client.get(f"/mensajes/{post.id}/{cliente.id}")

    assert resp.status_code == 403


def test_el_dueño_no_puede_conversar_consigo_mismo(client, crear_usuario, crear_post, login):
    autor = crear_usuario(username="autor")
    post = crear_post(autor.id)

    login(autor.id)
    resp = client.get(f"/mensajes/{post.id}/{autor.id}")

    assert resp.status_code == 404


def test_el_inbox_lista_conversaciones_como_cliente_y_como_dueño(
    client, db, crear_usuario, crear_post, login
):
    autor = crear_usuario(username="autor")
    cliente = crear_usuario(username="cliente")
    post = crear_post(autor.id, title="Panadería del barrio")
    db.session.add(Message(post_id=post.id, client_id=cliente.id, sender_id=cliente.id, body="Hola"))
    db.session.commit()

    login(autor.id)
    html = client.get("/mensajes/").get_data(as_text=True)

    assert "Panadería del barrio" in html


def test_el_polling_solo_devuelve_mensajes_posteriores(
    client, db, crear_usuario, crear_post, login
):
    autor = crear_usuario(username="autor")
    cliente = crear_usuario(username="cliente")
    post = crear_post(autor.id)
    primero = Message(post_id=post.id, client_id=cliente.id, sender_id=cliente.id, body="Uno")
    db.session.add(primero)
    db.session.commit()

    login(autor.id)
    client.post(f"/mensajes/{post.id}/{cliente.id}", data={"body": "Dos"})

    resp = client.get(f"/mensajes/{post.id}/{cliente.id}/nuevos?after={primero.id}")
    datos = resp.get_json()

    assert len(datos["items"]) == 1
    assert datos["items"][0]["body"] == "Dos"


# --------------------------------------------------------------- notificaciones

def test_el_badge_cuenta_mensajes_sin_leer_del_dueño(client, db, crear_usuario, crear_post, login):
    autor = crear_usuario(username="autor")
    cliente = crear_usuario(username="cliente")
    post = crear_post(autor.id)
    db.session.add(Message(post_id=post.id, client_id=cliente.id, sender_id=cliente.id, body="Hola"))
    db.session.commit()

    login(autor.id)
    datos = client.get("/mensajes/notificaciones").get_json()

    assert datos["unread_messages"] == 1
    assert datos["total"] == 1


def test_abrir_la_conversacion_marca_los_mensajes_como_leidos(
    client, db, crear_usuario, crear_post, login
):
    autor = crear_usuario(username="autor")
    cliente = crear_usuario(username="cliente")
    post = crear_post(autor.id)
    db.session.add(Message(post_id=post.id, client_id=cliente.id, sender_id=cliente.id, body="Hola"))
    db.session.commit()

    login(autor.id)
    client.get(f"/mensajes/{post.id}/{cliente.id}")  # abre la conversacion

    datos = client.get("/mensajes/notificaciones").get_json()
    assert datos["unread_messages"] == 0


def test_no_se_cuentan_los_mensajes_propios_como_sin_leer(
    client, db, crear_usuario, crear_post, login
):
    autor = crear_usuario(username="autor")
    cliente = crear_usuario(username="cliente")
    post = crear_post(autor.id)

    login(cliente.id)
    client.post(f"/mensajes/{post.id}/{cliente.id}", data={"body": "Hola"})

    datos = client.get("/mensajes/notificaciones").get_json()
    assert datos["unread_messages"] == 0


def test_el_badge_cuenta_resenias_sin_responder(client, db, crear_usuario, crear_post, login):
    autor = crear_usuario(username="autor")
    cliente = crear_usuario(username="cliente")
    post = crear_post(autor.id)
    db.session.add(Review(post_id=post.id, user_id=cliente.id, rating=4))
    db.session.commit()

    login(autor.id)
    datos = client.get("/mensajes/notificaciones").get_json()

    assert datos["unanswered_reviews"] == 1
    assert datos["total"] == 1


def test_una_resenia_respondida_no_cuenta_en_el_badge(
    client, db, crear_usuario, crear_post, login
):
    autor = crear_usuario(username="autor")
    cliente = crear_usuario(username="cliente")
    post = crear_post(autor.id)
    db.session.add(Review(post_id=post.id, user_id=cliente.id, rating=4, reply="Gracias"))
    db.session.commit()

    login(autor.id)
    datos = client.get("/mensajes/notificaciones").get_json()

    assert datos["unanswered_reviews"] == 0


# --------------------------------------------- ON DELETE CASCADE (FK 1451)

def test_se_puede_eliminar_un_post_con_mensajes(client, db, crear_usuario, crear_post, login):
    """Antes del fix, esto fallaba con IntegrityError 1451 en MySQL: el FK
    de messages.post_id era RESTRICT por default."""
    autor = crear_usuario(username="autor")
    cliente = crear_usuario(username="cliente")
    post = crear_post(autor.id)

    login(cliente.id)
    client.post(f"/mensajes/{post.id}/{cliente.id}", data={"body": "Hola"})
    assert Message.query.filter_by(post_id=post.id).count() == 1

    login(autor.id)
    resp = client.post(f"/blog/delete/{post.id}", follow_redirects=False)

    assert resp.status_code == 302
    assert Post.query.get(post.id) is None
    assert Message.query.filter_by(post_id=post.id).count() == 0
