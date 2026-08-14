"""Tests del perfil del emprendedor: contacto, avatar y sus emprendimientos."""

import io

from PIL import Image
from werkzeug.datastructures import FileStorage

from models.review import Review
from models.user import User


def test_editar_perfil_guarda_datos_de_contacto(client, db, crear_usuario, login):
    usuario = crear_usuario(username="tomy")
    login(usuario.id)

    client.post("/perfil/edit", data={
        "biography": "Hago pan artesanal",
        "phone": "261 555-1234",
        "whatsapp": "5492615551234",
        "instagram_url": "https://instagram.com/tomy",
        "facebook_url": "https://facebook.com/tomy",
        "twitter_url": "https://twitter.com/tomy",
        "address_street": "",
    })

    db.session.refresh(usuario)
    assert usuario.phone == "261 555-1234"
    assert usuario.whatsapp == "5492615551234"
    assert usuario.instagram_url == "https://instagram.com/tomy"


def test_el_perfil_publico_muestra_los_datos_de_contacto(client, db, crear_usuario):
    usuario = crear_usuario(username="tomy")
    usuario.whatsapp = "5492615551234"
    db.session.commit()

    html = client.get(f"/perfil/{usuario.id}").get_data(as_text=True)

    assert "5492615551234" in html


def test_el_perfil_renderiza_la_bio_con_formato(client, db, crear_usuario):
    usuario = crear_usuario(username="tomy")
    usuario.biography = "Somos **artesanales** desde 1990.\nVisitanos!"
    db.session.commit()

    html = client.get(f"/perfil/{usuario.id}").get_data(as_text=True)

    assert "<strong>artesanales</strong>" in html
    assert "1990.<br>Visitanos" in html


def test_el_perfil_no_ejecuta_html_inyectado_en_la_bio(client, db, crear_usuario):
    usuario = crear_usuario(username="tomy")
    usuario.biography = "<script>alert('xss')</script>"
    db.session.commit()

    html = client.get(f"/perfil/{usuario.id}").get_data(as_text=True)

    assert "<script>alert" not in html
    assert "&lt;script&gt;" in html


def test_editar_perfil_sube_un_avatar_valido(client, db, crear_usuario, login):
    usuario = crear_usuario(username="tomy")
    login(usuario.id)

    buffer = io.BytesIO()
    Image.new("RGB", (10, 10), "blue").save(buffer, format="PNG")
    buffer.seek(0)
    avatar = FileStorage(stream=buffer, filename="foto.png", content_type="image/png")

    client.post(
        "/perfil/edit",
        data={"biography": "Bio", "avatar": avatar},
        content_type="multipart/form-data",
    )

    db.session.refresh(usuario)
    assert usuario.avatar is not None


def test_editar_perfil_sube_una_portada_valida(client, db, crear_usuario, login):
    usuario = crear_usuario(username="tomy")
    login(usuario.id)

    buffer = io.BytesIO()
    Image.new("RGB", (1400, 400), "green").save(buffer, format="PNG")
    buffer.seek(0)
    portada = FileStorage(stream=buffer, filename="portada.png", content_type="image/png")

    client.post(
        "/perfil/edit",
        data={"biography": "Bio", "cover_image": portada},
        content_type="multipart/form-data",
    )

    db.session.refresh(usuario)
    assert usuario.cover_image is not None


def test_el_perfil_muestra_la_portada_propia(client, db, crear_usuario):
    usuario = crear_usuario(username="tomy")
    usuario.cover_image = "portada_de_prueba.png"
    db.session.commit()

    html = client.get(f"/perfil/{usuario.id}").get_data(as_text=True)

    assert "uploads/covers/portada_de_prueba.png" in html


def test_el_perfil_muestra_sus_emprendimientos_con_calificacion(
    client, db, crear_usuario, crear_post
):
    autor = crear_usuario(username="autor")
    cliente = crear_usuario(username="cliente")
    post = crear_post(autor.id, title="Panadería del barrio")
    db.session.add(Review(post_id=post.id, user_id=cliente.id, rating=5))
    db.session.commit()

    html = client.get(f"/perfil/{autor.id}").get_data(as_text=True)

    assert "Panadería del barrio" in html
    assert "5.0" in html


def test_el_dueño_ve_las_vistas_de_sus_posts_en_su_perfil(
    client, db, crear_usuario, crear_post, login
):
    autor = crear_usuario(username="autor")
    visitante = crear_usuario(username="visitante")
    post = crear_post(autor.id)

    login(visitante.id)
    client.get(f"/blog/{post.id}")

    login(autor.id)
    html = client.get(f"/perfil/{autor.id}").get_data(as_text=True)

    assert "1 vista" in html


def test_un_visitante_no_ve_las_vistas_en_el_perfil_ajeno(
    client, db, crear_usuario, crear_post
):
    """La metrica es para el dueño, no un dato publico."""
    autor = crear_usuario(username="autor")
    crear_post(autor.id)

    html = client.get(f"/perfil/{autor.id}").get_data(as_text=True)

    assert "vista" not in html


# --------------------------------------------------- historial de reseñas

def test_el_historial_junta_resenias_de_todos_los_emprendimientos(
    client, db, crear_usuario, crear_post
):
    autor = crear_usuario(username="autor")
    cliente1 = crear_usuario(username="cliente1")
    cliente2 = crear_usuario(username="cliente2")
    post1 = crear_post(autor.id, title="Panadería")
    post2 = crear_post(autor.id, title="Verdulería")

    db.session.add(Review(post_id=post1.id, user_id=cliente1.id, rating=5, comment="Excelente pan"))
    db.session.add(Review(post_id=post2.id, user_id=cliente2.id, rating=4, comment="Buena verdura"))
    db.session.commit()

    html = client.get(f"/perfil/{autor.id}/resenias").get_data(as_text=True)

    assert "Excelente pan" in html
    assert "Buena verdura" in html
    assert "Panadería" in html
    assert "Verdulería" in html


def test_el_historial_no_incluye_resenias_de_otros_emprendedores(
    client, db, crear_usuario, crear_post
):
    autor = crear_usuario(username="autor")
    otro_autor = crear_usuario(username="otro_autor")
    cliente = crear_usuario(username="cliente")
    post_propio = crear_post(autor.id, title="Mi negocio")
    post_ajeno = crear_post(otro_autor.id, title="Negocio ajeno")

    db.session.add(Review(post_id=post_propio.id, user_id=cliente.id, rating=5, comment="Mío"))
    db.session.add(Review(post_id=post_ajeno.id, user_id=cliente.id, rating=1, comment="Ajeno"))
    db.session.commit()

    html = client.get(f"/perfil/{autor.id}/resenias").get_data(as_text=True)

    assert "Mío" in html
    assert "Ajeno" not in html


def test_el_historial_muestra_la_respuesta_del_dueño(client, db, crear_usuario, crear_post):
    autor = crear_usuario(username="autor")
    cliente = crear_usuario(username="cliente")
    post = crear_post(autor.id)

    db.session.add(Review(
        post_id=post.id, user_id=cliente.id, rating=5, comment="Buenísimo",
        reply="Gracias por tu compra",
    ))
    db.session.commit()

    html = client.get(f"/perfil/{autor.id}/resenias").get_data(as_text=True)

    assert "Gracias por tu compra" in html


def test_el_historial_se_pagina(client, db, app, crear_usuario, crear_post):
    autor = crear_usuario(username="autor")
    por_pagina = app.config["POSTS_POR_PAGINA"]
    post = crear_post(autor.id)

    for numero in range(por_pagina + 2):
        cliente = crear_usuario(username=f"cliente{numero}")
        db.session.add(Review(post_id=post.id, user_id=cliente.id, rating=3, comment=f"Reseña {numero}"))
    db.session.commit()

    primera = client.get(f"/perfil/{autor.id}/resenias").get_data(as_text=True)
    segunda = client.get(f"/perfil/{autor.id}/resenias?page=2").get_data(as_text=True)

    assert primera.count("review-card") > 0
    assert "Página 2" in segunda


def test_el_perfil_linkea_al_historial_de_reseñas(client, crear_usuario, crear_post):
    autor = crear_usuario(username="autor")
    crear_post(autor.id)

    html = client.get(f"/perfil/{autor.id}").get_data(as_text=True)

    assert f'/perfil/{autor.id}/resenias' in html
