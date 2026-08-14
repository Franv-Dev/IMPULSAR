"""Tests de emprendimientos: CRUD, permisos y resenas."""

import re

import pytest

from models.post import Categorias, Post
from models.review import Review
from views.blog import get_post


# ------------------------------------------------------------------ unitarios

def test_el_post_guarda_al_autor_correcto(db, crear_usuario, crear_post):
    autor = crear_usuario(username="autor")
    post = crear_post(autor.id, title="Panadería")

    assert post.author == autor.id
    # La relacion evita tener que hacer User.query.get(post.author) a mano.
    assert post.author_user.username == "autor"


def test_get_post_bloquea_a_quien_no_es_el_autor(app, crear_usuario, crear_post):
    autor = crear_usuario(username="autor")
    otro = crear_usuario(username="otro")
    post = crear_post(autor.id)

    with app.test_request_context():
        from flask import g

        g.user = otro
        resultado = get_post(post.id, check_author=True)

    # No devuelve el post: devuelve una redireccion.
    assert not isinstance(resultado, Post)


# ------------------------------------------------------------------- listados

def test_el_listado_publico_no_requiere_login(client, crear_usuario, crear_post):
    autor = crear_usuario(username="autor")
    crear_post(autor.id, title="Panadería visible")

    resp = client.get("/blog/")

    assert resp.status_code == 200
    assert "Panadería visible" in resp.get_data(as_text=True)


def test_el_listado_muestra_el_autor_real_y_no_al_usuario_logueado(
    client, crear_usuario, crear_post, login
):
    """Antes el listado mostraba tu propio nombre como autor de todos los posts."""
    autor = crear_usuario(username="autorreal")
    visitante = crear_usuario(username="visitante")
    crear_post(autor.id, title="Panadería")

    login(visitante.id)
    html = client.get("/blog/").get_data(as_text=True)

    # Se mira solo el badge de autor: el nombre del usuario logueado aparece
    # legitimamente en la barra de navegacion, asi que no sirve buscarlo en
    # todo el HTML.
    autores_mostrados = re.findall(
        r'badge--author"[^>]*>\s*([^<\s]+)\s*<', html
    )

    assert autores_mostrados == ["autorreal"]


def test_la_api_de_posts_devuelve_json(client, crear_usuario, crear_post):
    autor = crear_usuario(username="autor")
    crear_post(autor.id, title="Panadería")

    resp = client.get("/api/posts/")

    assert resp.status_code == 200
    datos = resp.get_json()
    assert datos["items"][0]["title"] == "Panadería"
    assert datos["total"] == 1


# ----------------------------------------------------------------------- CRUD

def test_crear_requiere_login(client):
    resp = client.get("/blog/create", follow_redirects=False)

    assert resp.status_code == 302
    assert "/auth/login" in resp.headers["Location"]


def test_flujo_completo_crear_editar_eliminar(client, db, crear_usuario, login):
    autor = crear_usuario(username="autor")
    login(autor.id)

    # Crear
    resp = client.post("/blog/create", data={
        "title": "Mi emprendimiento",
        "body": "Una descripción",
    }, follow_redirects=False)
    assert resp.status_code == 302

    post = Post.query.filter_by(title="Mi emprendimiento").first()
    assert post is not None

    # Editar
    resp = client.post(f"/blog/update/{post.id}", data={
        "title": "Título editado",
        "body": "Contenido editado",
    }, follow_redirects=False)
    assert resp.status_code == 302

    db.session.refresh(post)
    assert post.title == "Título editado"

    # Eliminar: por GET no se debe poder
    assert client.get(f"/blog/delete/{post.id}").status_code == 405

    resp = client.post(f"/blog/delete/{post.id}", follow_redirects=False)
    assert resp.status_code == 302
    assert Post.query.get(post.id) is None


def test_no_se_puede_editar_el_emprendimiento_de_otro(
    client, db, crear_usuario, crear_post, login
):
    autor = crear_usuario(username="autor")
    intruso = crear_usuario(username="intruso")
    post = crear_post(autor.id, title="Original")

    login(intruso.id)
    client.post(f"/blog/update/{post.id}", data={"title": "Hackeado", "body": "x"})

    db.session.refresh(post)
    assert post.title == "Original"


def test_no_se_puede_eliminar_el_emprendimiento_de_otro(
    client, crear_usuario, crear_post, login
):
    autor = crear_usuario(username="autor")
    intruso = crear_usuario(username="intruso")
    post = crear_post(autor.id)

    login(intruso.id)
    client.post(f"/blog/delete/{post.id}")

    assert Post.query.get(post.id) is not None


def test_crear_sin_titulo_no_guarda_nada(client, crear_usuario, login):
    autor = crear_usuario(username="autor")
    login(autor.id)

    client.post("/blog/create", data={"title": "", "body": "Una descripción"})

    assert Post.query.count() == 0


# --------------------------------------------------------------------- resenas

def test_dejar_una_resenia(client, crear_usuario, crear_post, login):
    autor = crear_usuario(username="autor")
    cliente = crear_usuario(username="cliente")
    post = crear_post(autor.id)

    login(cliente.id)
    client.post(f"/blog/{post.id}/review", data={"rating": "5", "comment": "Excelente"})

    review = Review.query.filter_by(post_id=post.id, user_id=cliente.id).first()
    assert review.rating == 5
    assert review.comment == "Excelente"


def test_el_autor_no_puede_reseniar_su_propio_emprendimiento(
    client, crear_usuario, crear_post, login
):
    autor = crear_usuario(username="autor")
    post = crear_post(autor.id)

    login(autor.id)
    client.post(f"/blog/{post.id}/review", data={"rating": "5", "comment": "Soy genial"})

    assert Review.query.count() == 0


@pytest.mark.parametrize("rating", ["0", "6", "-1", "no-es-un-numero"])
def test_se_rechazan_ratings_invalidos(client, crear_usuario, crear_post, login, rating):
    autor = crear_usuario(username="autor")
    cliente = crear_usuario(username="cliente")
    post = crear_post(autor.id)

    login(cliente.id)
    client.post(f"/blog/{post.id}/review", data={"rating": rating, "comment": "x"})

    assert Review.query.count() == 0


def test_el_autor_de_la_resenia_puede_editarla(client, crear_usuario, crear_post, login):
    """Reenviar el formulario de reseña la actualiza (mismo endpoint add_review)."""
    autor = crear_usuario(username="autor")
    cliente = crear_usuario(username="cliente")
    post = crear_post(autor.id)

    login(cliente.id)
    client.post(f"/blog/{post.id}/review", data={"rating": "3", "comment": "Regular"})
    client.post(f"/blog/{post.id}/review", data={"rating": "5", "comment": "Mejoró mucho"})

    review = Review.query.filter_by(post_id=post.id, user_id=cliente.id).first()
    assert review.rating == 5
    assert review.comment == "Mejoró mucho"


def test_el_detalle_precarga_el_formulario_con_la_resenia_propia(
    client, crear_usuario, crear_post, login
):
    autor = crear_usuario(username="autor")
    cliente = crear_usuario(username="cliente")
    post = crear_post(autor.id)

    login(cliente.id)
    client.post(f"/blog/{post.id}/review", data={"rating": "4", "comment": "Muy bueno"})

    html = client.get(f"/blog/{post.id}").get_data(as_text=True)

    assert "Actualizar reseña" in html
    assert "Muy bueno" in html


def test_el_autor_de_la_resenia_puede_eliminarla(client, crear_usuario, crear_post, login):
    autor = crear_usuario(username="autor")
    cliente = crear_usuario(username="cliente")
    post = crear_post(autor.id)

    login(cliente.id)
    client.post(f"/blog/{post.id}/review", data={"rating": "4", "comment": "Bien"})
    review = Review.query.filter_by(post_id=post.id, user_id=cliente.id).first()

    client.post(f"/blog/review/{review.id}/delete")

    assert Review.query.get(review.id) is None


def test_un_extranio_no_puede_eliminar_la_resenia_de_otro(
    client, crear_usuario, crear_post, login
):
    autor = crear_usuario(username="autor")
    cliente = crear_usuario(username="cliente")
    intruso = crear_usuario(username="intruso")
    post = crear_post(autor.id)

    login(cliente.id)
    client.post(f"/blog/{post.id}/review", data={"rating": "4", "comment": "Bien"})
    review = Review.query.filter_by(post_id=post.id, user_id=cliente.id).first()

    login(intruso.id)
    client.post(f"/blog/review/{review.id}/delete")

    assert Review.query.get(review.id) is not None


def test_una_segunda_resenia_actualiza_la_primera(client, crear_usuario, crear_post, login):
    """Sin esto un usuario podria inflar el promedio dejando varias resenas."""
    autor = crear_usuario(username="autor")
    cliente = crear_usuario(username="cliente")
    post = crear_post(autor.id)

    login(cliente.id)
    client.post(f"/blog/{post.id}/review", data={"rating": "1", "comment": "Malo"})
    client.post(f"/blog/{post.id}/review", data={"rating": "5", "comment": "Me arrepentí"})

    reviews = Review.query.filter_by(post_id=post.id, user_id=cliente.id).all()
    assert len(reviews) == 1
    assert reviews[0].rating == 5


def test_el_detalle_muestra_el_promedio_de_estrellas(
    client, db, crear_usuario, crear_post, login
):
    autor = crear_usuario(username="autor")
    post = crear_post(autor.id)

    for indice, puntaje in enumerate([4, 5]):
        cliente = crear_usuario(username=f"cliente{indice}")
        db.session.add(Review(post_id=post.id, user_id=cliente.id, rating=puntaje))
    db.session.commit()

    html = client.get(f"/blog/{post.id}").get_data(as_text=True)

    assert "4.5" in html


# ---------------------------------------------------------- paginacion y busqueda

def test_el_listado_se_pagina(client, app, crear_usuario, crear_post):
    autor = crear_usuario(username="autor")
    por_pagina = app.config["POSTS_POR_PAGINA"]
    for numero in range(por_pagina + 3):
        crear_post(autor.id, title=f"Emprendimiento {numero}")

    primera = client.get("/blog/").get_data(as_text=True)
    segunda = client.get("/blog/?page=2").get_data(as_text=True)

    assert primera.count('class="card"') == por_pagina
    assert segunda.count('class="card"') == 3
    assert "Página 2 de 2" in segunda


def test_la_api_pagina_los_resultados(client, crear_usuario, crear_post):
    autor = crear_usuario(username="autor")
    for numero in range(5):
        crear_post(autor.id, title=f"Emprendimiento {numero}")

    datos = client.get("/api/posts/?per_page=2&page=2").get_json()

    assert len(datos["items"]) == 2
    assert datos["page"] == 2
    assert datos["pages"] == 3
    assert datos["total"] == 5
    assert datos["has_next"] is True
    assert datos["has_prev"] is True


def test_la_api_no_permite_pedir_paginas_gigantes(client, crear_usuario, crear_post):
    """Sin tope, un ?per_page=999999 se lleva la base entera en una consulta."""
    autor = crear_usuario(username="autor")
    crear_post(autor.id)

    datos = client.get("/api/posts/?per_page=999999").get_json()

    assert datos["per_page"] == 50


# -------------------------------------------------------- respuesta a resenas

def test_el_dueño_puede_responder_una_resenia(client, db, crear_usuario, crear_post, login):
    autor = crear_usuario(username="autor")
    cliente = crear_usuario(username="cliente")
    post = crear_post(autor.id)
    review = Review(post_id=post.id, user_id=cliente.id, rating=4, comment="Bien")
    db.session.add(review)
    db.session.commit()

    login(autor.id)
    client.post(f"/blog/review/{review.id}/reply", data={"reply": "¡Gracias por tu visita!"})

    db.session.refresh(review)
    assert review.reply == "¡Gracias por tu visita!"
    assert review.replied_at is not None


def test_un_extranio_no_puede_responder_una_resenia(client, db, crear_usuario, crear_post, login):
    autor = crear_usuario(username="autor")
    cliente = crear_usuario(username="cliente")
    intruso = crear_usuario(username="intruso")
    post = crear_post(autor.id)
    review = Review(post_id=post.id, user_id=cliente.id, rating=4, comment="Bien")
    db.session.add(review)
    db.session.commit()

    login(intruso.id)
    client.post(f"/blog/review/{review.id}/reply", data={"reply": "Intento ajeno"})

    db.session.refresh(review)
    assert review.reply is None


def test_no_se_puede_responder_con_texto_vacio(client, db, crear_usuario, crear_post, login):
    autor = crear_usuario(username="autor")
    cliente = crear_usuario(username="cliente")
    post = crear_post(autor.id)
    review = Review(post_id=post.id, user_id=cliente.id, rating=4, comment="Bien")
    db.session.add(review)
    db.session.commit()

    login(autor.id)
    client.post(f"/blog/review/{review.id}/reply", data={"reply": "   "})

    db.session.refresh(review)
    assert review.reply is None


def test_el_detalle_muestra_la_respuesta_publica(client, db, crear_usuario, crear_post, login):
    autor = crear_usuario(username="autor")
    cliente = crear_usuario(username="cliente")
    post = crear_post(autor.id)
    review = Review(
        post_id=post.id, user_id=cliente.id, rating=5, comment="Genial",
        reply="Gracias, vení cuando quieras",
    )
    db.session.add(review)
    db.session.commit()

    html = client.get(f"/blog/{post.id}").get_data(as_text=True)

    assert "Gracias, vení cuando quieras" in html


# ---------------------------------------------------------------- busqueda API

def test_la_api_busca_por_titulo_y_descripcion(client, crear_usuario, crear_post):
    autor = crear_usuario(username="autor")
    crear_post(autor.id, title="Panadería del barrio", body="Pan artesanal")
    crear_post(autor.id, title="Taller mecánico", body="Arreglamos autos")

    por_titulo = client.get("/api/posts/?q=panader").get_json()
    por_cuerpo = client.get("/api/posts/?q=autos").get_json()
    sin_resultados = client.get("/api/posts/?q=zzzzz").get_json()

    assert por_titulo["total"] == 1
    assert por_titulo["items"][0]["title"] == "Panadería del barrio"
    assert por_cuerpo["total"] == 1
    assert por_cuerpo["items"][0]["title"] == "Taller mecánico"
    assert sin_resultados["total"] == 0


# ------------------------------------------------------------------- categorias

def test_crear_guarda_la_categoria_elegida(client, crear_usuario, login):
    autor = crear_usuario(username="autor")
    login(autor.id)

    client.post("/blog/create", data={
        "title": "Dulces Mendoza", "body": "Alfajores", "category": Categorias.ALIMENTOS,
    })

    post = Post.query.filter_by(title="Dulces Mendoza").first()
    assert post.category == Categorias.ALIMENTOS


def test_una_categoria_invalida_cae_en_otros(client, crear_usuario, login):
    """El valor viaja como texto libre desde el form: no hay que confiar en el cliente."""
    autor = crear_usuario(username="autor")
    login(autor.id)

    client.post("/blog/create", data={
        "title": "Emprendimiento raro", "body": "x", "category": "no-es-una-categoria-real",
    })

    post = Post.query.filter_by(title="Emprendimiento raro").first()
    assert post.category == Categorias.OTROS


def test_editar_actualiza_la_categoria(client, db, crear_usuario, crear_post, login):
    autor = crear_usuario(username="autor")
    post = crear_post(autor.id, category=Categorias.OTROS)

    login(autor.id)
    client.post(f"/blog/update/{post.id}", data={
        "title": post.title, "body": post.body, "category": Categorias.TECNOLOGIA,
    })

    db.session.refresh(post)
    assert post.category == Categorias.TECNOLOGIA


def test_el_listado_filtra_por_categoria(client, crear_usuario, crear_post):
    autor = crear_usuario(username="autor")
    crear_post(autor.id, title="Panadería", category=Categorias.ALIMENTOS)
    crear_post(autor.id, title="Reparación de PCs", category=Categorias.TECNOLOGIA)

    html = client.get(f"/blog/?category={Categorias.ALIMENTOS}").get_data(as_text=True)

    assert "Panadería" in html
    assert "Reparación de PCs" not in html


def test_el_listado_combina_categoria_y_busqueda(client, crear_usuario, crear_post):
    autor = crear_usuario(username="autor")
    crear_post(autor.id, title="Panadería del barrio", category=Categorias.ALIMENTOS)
    crear_post(autor.id, title="Verdulería central", category=Categorias.ALIMENTOS)

    html = client.get(f"/blog/?category={Categorias.ALIMENTOS}&q=barrio").get_data(as_text=True)

    assert "Panadería del barrio" in html
    assert "Verdulería central" not in html


def test_la_paginacion_conserva_los_filtros_activos(client, app, crear_usuario, crear_post):
    autor = crear_usuario(username="autor")
    por_pagina = app.config["POSTS_POR_PAGINA"]
    for numero in range(por_pagina + 2):
        crear_post(autor.id, title=f"Alimento {numero}", category=Categorias.ALIMENTOS)

    html = client.get(f"/blog/?category={Categorias.ALIMENTOS}").get_data(as_text=True)

    assert f"category={Categorias.ALIMENTOS}" in html
    assert "page=2" in html


def test_la_api_de_posts_filtra_por_categoria(client, crear_usuario, crear_post):
    autor = crear_usuario(username="autor")
    crear_post(autor.id, title="Panadería", category=Categorias.ALIMENTOS)
    crear_post(autor.id, title="Reparación de PCs", category=Categorias.TECNOLOGIA)

    datos = client.get(f"/api/posts/?category={Categorias.TECNOLOGIA}").get_json()

    assert datos["total"] == 1
    assert datos["items"][0]["title"] == "Reparación de PCs"


# --------------------------------------------------------------- cercania

def test_ordena_por_distancia_cuando_se_pasan_lat_lon(client, crear_usuario, crear_post):
    autor = crear_usuario(username="autor")
    # Referencia: Ciudad de Mendoza. "Cerca" queda a metros, "Lejos" a ~90km.
    crear_post(autor.id, title="Lejos", latitude=-33.5, longitude=-69.5)
    crear_post(autor.id, title="Cerca", latitude=-32.891, longitude=-68.841)

    html = client.get("/blog/?lat=-32.89&lon=-68.84").get_data(as_text=True)

    assert html.index("Cerca") < html.index("Lejos")


def test_excluye_posts_sin_ubicacion_al_buscar_por_cercania(client, crear_usuario, crear_post):
    autor = crear_usuario(username="autor")
    crear_post(autor.id, title="Con ubicación", latitude=-32.891, longitude=-68.841)
    crear_post(autor.id, title="Sin ubicación")

    html = client.get("/blog/?lat=-32.89&lon=-68.84").get_data(as_text=True)

    assert "Con ubicación" in html
    assert "Sin ubicación" not in html


def test_la_direccion_de_texto_sin_maptiler_key_no_rompe_el_listado(
    client, crear_usuario, crear_post
):
    """En testing no hay MAPTILER_KEY: cae al orden por defecto en vez de fallar."""
    autor = crear_usuario(username="autor")
    crear_post(autor.id, title="Panadería del barrio")

    resp = client.get("/blog/?near=Av+San+Martin+123")

    assert resp.status_code == 200
    assert "Panadería del barrio" in resp.get_data(as_text=True)


def test_sin_filtro_de_cercania_el_orden_por_defecto_no_cambia(
    client, crear_usuario, crear_post
):
    autor = crear_usuario(username="autor")
    crear_post(autor.id, title="Primero", latitude=-32.891, longitude=-68.841)
    crear_post(autor.id, title="Segundo")

    html = client.get("/blog/").get_data(as_text=True)

    # Orden por fecha de creacion (mas nuevo primero), no por distancia.
    assert html.index("Segundo") < html.index("Primero")
