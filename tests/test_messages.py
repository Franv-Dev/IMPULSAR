"""Tests del chat simple entre cliente y emprendedor."""

from models.message import Message


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
