"""Tests de emprendimientos: CRUD, permisos y resenas."""

import re

import pytest
from sqlalchemy import event

from app.blog import consultas, reglas
from app.blog.reglas import MAX_TITULO
from app.blog.modelo_post import Categorias, Post
from app.blog.modelo_resenia import Review
from models.user import User
from app.blog.vistas import get_post
from app.servicios.modelo import Service
from models.product import Product


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


def test_la_api_de_posts_incluye_la_etiqueta_de_categoria(client, crear_usuario, crear_post):
    """El buscador AJAX del home usa este campo en vez de un texto fijo."""
    autor = crear_usuario(username="autor")
    crear_post(autor.id, title="Dulces Mendoza", category=Categorias.ALIMENTOS)

    datos = client.get("/api/posts/").get_json()

    assert datos["items"][0]["category"] == Categorias.ALIMENTOS
    assert datos["items"][0]["category_label"] == "Alimentos"


def test_la_api_no_expone_views_count_a_terceros(client, crear_usuario, crear_post):
    autor = crear_usuario(username="autor")
    otro = crear_usuario(username="otro")
    post = crear_post(autor.id)

    # Anonimo
    datos_anonimo = client.get("/api/posts/").get_json()
    assert "views_count" not in datos_anonimo["items"][0]

    # Logueado, pero no es el dueño
    login_resp = client.post("/auth/login", data={"username": "otro", "password": "secreta123"})
    datos_otro = client.get("/api/posts/").get_json()
    assert "views_count" not in datos_otro["items"][0]

    datos_detalle = client.get(f"/api/posts/{post.id}").get_json()
    assert "views_count" not in datos_detalle


def test_la_api_expone_views_count_al_dueño(client, crear_usuario, crear_post, login):
    autor = crear_usuario(username="autor")
    post = crear_post(autor.id)

    login(autor.id)
    datos_listado = client.get("/api/posts/").get_json()
    assert datos_listado["items"][0]["views_count"] == 0

    datos_detalle = client.get(f"/api/posts/{post.id}").get_json()
    assert datos_detalle["views_count"] == 0


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


def test_crear_con_un_titulo_mas_largo_que_la_columna_no_guarda_nada(
    client, crear_usuario, login
):
    """Se corta antes del INSERT y no se confia en que la base avise: MySQL
    trunca o falla segun el sql_mode con el que este levantado, asi que el
    nombre se guardaria cortado a la mitad sin aviso, o el usuario veria un 500
    en vez de un error del formulario."""
    autor = crear_usuario(username="autor")
    login(autor.id)

    respuesta = client.post("/blog/create", data={
        "title": "a" * (MAX_TITULO + 1), "body": "Una descripción",
    })

    assert Post.query.count() == 0
    assert str(MAX_TITULO) in respuesta.get_data(as_text=True)


def test_crear_con_un_titulo_del_largo_exacto_de_la_columna_guarda(
    client, crear_usuario, login
):
    """El borde del anterior: el maximo entra, no se rechaza por empatar."""
    autor = crear_usuario(username="autor")
    login(autor.id)

    client.post("/blog/create", data={
        "title": "a" * MAX_TITULO, "body": "Una descripción",
    })

    assert Post.query.count() == 1


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


def test_una_resenia_recien_creada_no_tiene_updated_at(client, crear_usuario, crear_post, login):
    autor = crear_usuario(username="autor")
    cliente = crear_usuario(username="cliente")
    post = crear_post(autor.id)

    login(cliente.id)
    client.post(f"/blog/{post.id}/review", data={"rating": "4", "comment": "Bien"})

    review = Review.query.filter_by(post_id=post.id, user_id=cliente.id).first()
    assert review.updated_at is None


def test_editar_la_resenia_marca_updated_at(client, crear_usuario, crear_post, login):
    autor = crear_usuario(username="autor")
    cliente = crear_usuario(username="cliente")
    post = crear_post(autor.id)

    login(cliente.id)
    client.post(f"/blog/{post.id}/review", data={"rating": "3", "comment": "Regular"})
    client.post(f"/blog/{post.id}/review", data={"rating": "5", "comment": "Mejoró mucho"})

    review = Review.query.filter_by(post_id=post.id, user_id=cliente.id).first()
    assert review.updated_at is not None


def test_editar_una_resenia_respondida_limpia_la_respuesta(
    client, db, crear_usuario, crear_post, login
):
    """Si el contenido de la reseña cambia, la respuesta vieja ya no aplica."""
    autor = crear_usuario(username="autor")
    cliente = crear_usuario(username="cliente")
    post = crear_post(autor.id)

    login(cliente.id)
    client.post(f"/blog/{post.id}/review", data={"rating": "1", "comment": "Malo"})
    review = Review.query.filter_by(post_id=post.id, user_id=cliente.id).first()

    login(autor.id)
    client.post(f"/blog/review/{review.id}/reply", data={"reply": "Lamento tu experiencia"})

    login(cliente.id)
    client.post(f"/blog/{post.id}/review", data={"rating": "5", "comment": "Me arrepentí, ahora es excelente"})

    db.session.refresh(review)
    assert review.reply is None
    assert review.replied_at is None


def test_el_detalle_muestra_editado_cuando_corresponde(client, crear_usuario, crear_post, login):
    autor = crear_usuario(username="autor")
    cliente = crear_usuario(username="cliente")
    post = crear_post(autor.id)

    login(cliente.id)
    client.post(f"/blog/{post.id}/review", data={"rating": "3", "comment": "Regular"})

    sin_editar = client.get(f"/blog/{post.id}").get_data(as_text=True)
    assert "(editado)" not in sin_editar

    client.post(f"/blog/{post.id}/review", data={"rating": "5", "comment": "Mejoró"})

    editado = client.get(f"/blog/{post.id}").get_data(as_text=True)
    assert "(editado)" in editado


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

    # .ficha es la tarjeta del listado (la horizontal de la pantalla
    # "Explorar"). No es la misma clase que .card, que es la tarjeta vertical
    # del home y del detalle.
    assert primera.count('class="ficha"') == por_pagina
    assert segunda.count('class="ficha"') == 3
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


# ------------------------------------------------- filtro "con reseñas"

def _con_resenia(db, post, usuario, puntaje=4):
    db.session.add(Review(post_id=post.id, user_id=usuario.id, rating=puntaje))
    db.session.commit()


def test_con_resenias_deja_solo_los_que_tienen_alguna(
    app, db, crear_usuario, crear_post
):
    autor = crear_usuario(username="autor")
    cliente = crear_usuario(username="cliente")
    resenado = crear_post(autor.id, title="Con reseñas")
    crear_post(autor.id, title="Sin reseñas")
    _con_resenia(db, resenado, cliente)

    paginacion, _ = consultas.buscar_posts(
        busqueda=None, categoria=None, lat=None, lon=None,
        pagina=1, por_pagina=20, con_resenias=True,
    )

    titulos = [fila[0].title for fila in paginacion.items]
    assert titulos == ["Con reseñas"]


def test_sin_el_filtro_vuelven_tambien_los_que_no_tienen_resenias(
    app, db, crear_usuario, crear_post
):
    """El default no cambia lo que ya hacia el listado."""
    autor = crear_usuario(username="autor")
    cliente = crear_usuario(username="cliente")
    resenado = crear_post(autor.id, title="Con reseñas")
    crear_post(autor.id, title="Sin reseñas")
    _con_resenia(db, resenado, cliente)

    paginacion, _ = consultas.buscar_posts(
        busqueda=None, categoria=None, lat=None, lon=None,
        pagina=1, por_pagina=20,
    )

    titulos = sorted(fila[0].title for fila in paginacion.items)
    assert titulos == ["Con reseñas", "Sin reseñas"]


def test_con_resenias_no_duplica_filas_cuando_hay_varias(
    app, db, crear_usuario, crear_post
):
    """El filtro va sobre la subquery agrupada, asi que el post viene una vez.

    Si en vez de eso se joineara reviews directo, un post con tres reseñas
    apareceria tres veces en el listado.
    """
    autor = crear_usuario(username="autor")
    post = crear_post(autor.id, title="Muy reseñado")
    for numero in range(3):
        cliente = crear_usuario(username=f"cliente{numero}")
        _con_resenia(db, post, cliente)

    paginacion, _ = consultas.buscar_posts(
        busqueda=None, categoria=None, lat=None, lon=None,
        pagina=1, por_pagina=20, con_resenias=True,
    )

    assert [fila[0].title for fila in paginacion.items] == ["Muy reseñado"]


# ------------------------------------------------------ radio de distancia

# Referencia de todos estos: Ciudad de Mendoza. "Cerca" queda a metros y
# "Lejos" a unos 90 km, los mismos puntos que usan los tests de orden.
CERCA = {"latitude": -32.891, "longitude": -68.841}
LEJOS = {"latitude": -33.5, "longitude": -69.5}
DESDE = "lat=-32.89&lon=-68.84"


def test_el_radio_deja_afuera_lo_que_esta_mas_lejos(client, crear_usuario, crear_post):
    autor = crear_usuario(username="autor")
    crear_post(autor.id, title="Acá nomás", **CERCA)
    crear_post(autor.id, title="A noventa km", **LEJOS)

    html = client.get(f"/blog/?{DESDE}&radio=5").get_data(as_text=True)

    assert "Acá nomás" in html
    assert "A noventa km" not in html


def test_el_radio_mas_grande_alcanza_para_los_dos(client, crear_usuario, crear_post):
    """Que el de 5 km lo excluya tiene que ser por la distancia, no porque si."""
    autor = crear_usuario(username="autor")
    crear_post(autor.id, title="Acá nomás", **CERCA)
    crear_post(autor.id, title="A ocho km", latitude=-32.96, longitude=-68.841)

    html = client.get(f"/blog/?{DESDE}&radio=10").get_data(as_text=True)

    assert "Acá nomás" in html
    assert "A ocho km" in html


def test_sin_radio_no_se_descarta_nada_por_lejos(client, crear_usuario, crear_post):
    """El comportamiento de hoy: ordena por cercania pero los trae a todos."""
    autor = crear_usuario(username="autor")
    crear_post(autor.id, title="Acá nomás", **CERCA)
    crear_post(autor.id, title="A noventa km", **LEJOS)

    html = client.get(f"/blog/?{DESDE}").get_data(as_text=True)

    assert "Acá nomás" in html
    assert "A noventa km" in html
    assert html.index("Acá nomás") < html.index("A noventa km")


def test_el_radio_sin_coordenadas_no_hace_nada(client, crear_usuario, crear_post):
    """Sin lat/lon no hay desde donde medir: se ignora en vez de vaciar todo."""
    autor = crear_usuario(username="autor")
    crear_post(autor.id, title="Acá nomás", **CERCA)
    crear_post(autor.id, title="A noventa km", **LEJOS)

    html = client.get("/blog/?radio=1").get_data(as_text=True)

    assert "Acá nomás" in html
    assert "A noventa km" in html


@pytest.mark.parametrize("radio", ["7", "0", "-5", "99999", "abc", ""])
def test_un_radio_que_no_esta_en_la_lista_se_ignora(
    client, crear_usuario, crear_post, radio
):
    """Vale lo mismo que no mandar radio, no filtrar con un numero cualquiera."""
    autor = crear_usuario(username="autor")
    crear_post(autor.id, title="Acá nomás", **CERCA)
    crear_post(autor.id, title="A noventa km", **LEJOS)

    html = client.get(f"/blog/?{DESDE}&radio={radio}").get_data(as_text=True)

    assert "Acá nomás" in html
    assert "A noventa km" in html


def test_el_radio_se_combina_con_el_filtro_de_resenias(
    app, db, crear_usuario, crear_post
):
    autor = crear_usuario(username="autor")
    cliente = crear_usuario(username="cliente")
    cerca_con = crear_post(autor.id, title="Cerca y reseñado", **CERCA)
    crear_post(autor.id, title="Cerca sin reseñas", **CERCA)
    lejos_con = crear_post(autor.id, title="Lejos y reseñado", **LEJOS)
    _con_resenia(db, cerca_con, cliente)
    _con_resenia(db, lejos_con, cliente)

    paginacion, ordenado = consultas.buscar_posts(
        busqueda=None, categoria=None, lat=-32.89, lon=-68.84,
        pagina=1, por_pagina=20, con_resenias=True, radio_km=5,
    )

    assert ordenado is True
    assert [fila[0].title for fila in paginacion.items] == ["Cerca y reseñado"]


# --------------------------------------- el panel de filtros contra la query

# Los dos controles que la pantalla dibujaba apagados y ahora mandan. Lo que se
# prueba aca no es el filtro (eso esta mas arriba, contra buscar_posts) sino el
# cableado: que el formulario mande lo que la consulta espera y que la pantalla
# se repinte con lo que quedo aplicado.


def _marcado(html, name):
    """El value del input `name` que viene checked, o None si no hay ninguno."""
    for etiqueta in re.findall(r'<input[^>]*\bname="{}"[^>]*>'.format(name), html):
        if "checked" in etiqueta:
            return re.search(r'value="([^"]*)"', etiqueta).group(1)
    return None


def test_el_radio_viaja_en_km_enteros_y_no_como_etiqueta(client):
    """El backend espera reglas.RADIOS_KM. Un value de "5 km" no filtra nada.

    Y no falla en ningun lado: leer_cercania lo lee con type=int, "5 km" vuelve
    None y el listado sale sin acotar, como si el usuario no hubiera elegido.
    """
    html = client.get("/blog/").get_data(as_text=True)

    for km in reglas.RADIOS_KM:
        assert 'name="radio" value="{}"'.format(km) in html
    assert 'value="1 km"' not in html


def test_los_dos_filtros_nuevos_ya_no_estan_apagados(client):
    html = client.get("/blog/").get_data(as_text=True)

    assert '<fieldset class="filtros__radios">' in html
    assert re.search(r'name="con_resenias"[^>]*disabled', html) is None


def test_solo_verificados_sigue_apagado(client):
    """Post no tiene marca de verificacion, asi que ese filtro no puede viajar.

    "Abierto ahora" ya no esta en la lista: se cableo contra los horarios del
    autor (ver los tests de mas abajo) y por eso ahora si puede viajar.
    """
    html = client.get("/blog/").get_data(as_text=True)

    assert re.search(r'name="solo_verificados"[^>]*disabled', html)
    assert re.search(r'name="abierto_ahora"[^>]*disabled', html) is None


def test_el_aviso_del_grupo_nombra_al_filtro_que_falta(client):
    """"Estos dos todavía no filtran" no decia cuales eran los dos.

    Ahora ademas quedo uno solo, asi que el aviso tiene que nombrarlo. Se
    escribe "Solo verificados" (la etiqueta del control, en minuscula) y no
    "Verificado": esa palabra en el listado es justamente la que fija
    test_el_listado_no_dice_que_un_emprendimiento_esta_verificado, porque un
    Post no tiene verificacion que afirmar.
    """
    html = client.get("/blog/").get_data(as_text=True)

    assert "Solo verificados» todavía no filtra" in html
    assert "Estos dos" not in html
    # La misma regla del otro test, para que el aviso no la rompa de costado.
    assert "Verificado" not in html


def test_sin_radio_en_la_url_queda_marcado_toda(client):
    html = client.get("/blog/").get_data(as_text=True)

    assert _marcado(html, "radio") == ""


def test_el_radio_de_la_url_queda_marcado(client):
    html = client.get("/blog/?{}&radio=5".format(DESDE)).get_data(as_text=True)

    assert _marcado(html, "radio") == "5"


def test_un_radio_invalido_repinta_toda(client):
    """Se ignora para filtrar (mas arriba) y tampoco se le repinta al usuario."""
    html = client.get("/blog/?{}&radio=7".format(DESDE)).get_data(as_text=True)

    assert _marcado(html, "radio") == ""


def test_el_checkbox_de_resenias_llega_hasta_la_consulta(
    app, db, client, crear_usuario, crear_post
):
    autor = crear_usuario(username="autor")
    cliente = crear_usuario(username="cliente")
    resenado = crear_post(autor.id, title="Panadería reseñada")
    crear_post(autor.id, title="Panadería recién abierta")
    _con_resenia(db, resenado, cliente)

    html = client.get("/blog/?con_resenias=1").get_data(as_text=True)

    assert "Panadería reseñada" in html
    assert "Panadería recién abierta" not in html


def test_sin_el_checkbox_el_listado_los_trae_a_los_dos(
    app, db, client, crear_usuario, crear_post
):
    autor = crear_usuario(username="autor")
    cliente = crear_usuario(username="cliente")
    resenado = crear_post(autor.id, title="Panadería reseñada")
    crear_post(autor.id, title="Panadería recién abierta")
    _con_resenia(db, resenado, cliente)

    html = client.get("/blog/").get_data(as_text=True)

    assert "Panadería reseñada" in html
    assert "Panadería recién abierta" in html


def test_el_checkbox_de_resenias_queda_marcado(client):
    html = client.get("/blog/?con_resenias=1").get_data(as_text=True)

    assert _marcado(html, "con_resenias") == "1"


def test_los_dos_filtros_nuevos_se_pueden_sacar_de_a_uno(client):
    """Aplicados salen como chip, igual que el texto, el rubro y la cercania."""
    html = client.get(
        "/blog/?{}&radio=5&con_resenias=1".format(DESDE)
    ).get_data(as_text=True)

    assert "Hasta 5 km" in html
    assert 'aria-label="Quitar el filtro de radio"' in html
    assert 'aria-label="Quitar el filtro de reseñas"' in html


def test_sin_coordenadas_el_radio_no_pinta_su_chip(client):
    """Un chip que anuncia un filtro que no se aplico es peor que no tenerlo.

    /blog/?radio=1 sin lat ni lon mostraba "Hasta 1 km" pero la consulta
    ignoraba el radio (sin coordenadas no hay desde donde medir), asi que el
    listado venia entero y el chip decia otra cosa.
    """
    html = client.get("/blog/?radio=1").get_data(as_text=True)

    assert "Hasta 1 km" not in html
    assert 'aria-label="Quitar el filtro de radio"' not in html
    # Y sin ningun otro filtro puesto, tampoco queda la fila de chips vacia
    # con su "Limpiar" al lado.
    assert 'class="filtros__limpiar"' not in html


def test_con_una_direccion_geocodificada_el_radio_si_pinta_su_chip(
    client, monkeypatch
):
    """Las coordenadas de una direccion las resuelve la vista y no estan en la URL.

    Por eso la condicion del chip mira si la consulta ordeno por distancia y no
    request.args: con "near" cargado el radio SI acota, y el chip corresponde.
    """
    monkeypatch.setattr(
        "app.blog.vistas.get_coordinates_from_address",
        lambda direccion, clave: (-34.6, -58.4),
    )

    html = client.get("/blog/?near=Obelisco&radio=5").get_data(as_text=True)

    assert "Hasta 5 km" in html


# ------------------------------------------------------------------ compartir

def test_la_tarjeta_incluye_el_link_para_compartir(client, crear_usuario, crear_post):
    autor = crear_usuario(username="autor")
    post = crear_post(autor.id, title="Panadería del barrio")

    html = client.get("/blog/").get_data(as_text=True)

    assert f'data-share-url="http://localhost/blog/{post.id}"' in html


def test_el_detalle_incluye_el_link_para_compartir(client, crear_usuario, crear_post):
    autor = crear_usuario(username="autor")
    post = crear_post(autor.id, title="Panadería del barrio")

    html = client.get(f"/blog/{post.id}").get_data(as_text=True)

    assert f'data-share-url="http://localhost/blog/{post.id}"' in html


# ------------------------------------------------------------- metricas de vistas

def test_ver_el_detalle_suma_una_vista(client, db, crear_usuario, crear_post):
    autor = crear_usuario(username="autor")
    post = crear_post(autor.id)

    client.get(f"/blog/{post.id}")

    db.session.refresh(post)
    assert post.views_count == 1


def test_varias_vistas_se_acumulan(client, db, crear_usuario, crear_post):
    autor = crear_usuario(username="autor")
    post = crear_post(autor.id)

    client.get(f"/blog/{post.id}")
    client.get(f"/blog/{post.id}")
    client.get(f"/blog/{post.id}")

    db.session.refresh(post)
    assert post.views_count == 3


def test_el_dueño_no_suma_vistas_al_ver_su_propio_post(client, db, crear_usuario, crear_post, login):
    autor = crear_usuario(username="autor")
    post = crear_post(autor.id)

    login(autor.id)
    client.get(f"/blog/{post.id}")
    client.get(f"/blog/{post.id}")

    db.session.refresh(post)
    assert post.views_count == 0


def test_las_vistas_de_otro_usuario_si_se_cuentan(client, db, crear_usuario, crear_post, login):
    autor = crear_usuario(username="autor")
    visitante = crear_usuario(username="visitante")
    post = crear_post(autor.id)

    login(visitante.id)
    client.get(f"/blog/{post.id}")

    db.session.refresh(post)
    assert post.views_count == 1


def test_las_vistas_se_muestran_en_mis_emprendimientos(client, crear_usuario, crear_post, login):
    autor = crear_usuario(username="autor")
    visitante = crear_usuario(username="visitante")
    post = crear_post(autor.id)

    login(visitante.id)
    client.get(f"/blog/{post.id}")

    login(autor.id)
    html = client.get("/blog/mis-emprendimientos").get_data(as_text=True)

    # El numero y la palabra son dos elementos distintos desde el rediseño (la
    # metrica es un valor grande con su etiqueta chica abajo), asi que se
    # buscan por separado en vez de como "1 vista".
    assert '<span class="metrica__valor">1</span>' in html
    assert '<span class="metrica__label">vista</span>' in html


def test_mis_emprendimientos_no_consulta_de_mas_por_cada_fila(
    app, client, crear_usuario, crear_post, login, db
):
    """El listado cuesta lo mismo con 3 emprendimientos que con 6.

    Las metricas de cada fila (reseñas, promedio, tamaño del catalogo) salian
    de una consulta por post: la pagina crecia cuatro consultas por fila. Lo
    que se fija aca no es un numero de consultas, sino que ese numero NO
    dependa de cuantos emprendimientos tenga el vendedor.
    """
    autor = crear_usuario(username="autor")
    login(autor.id)

    def consultas_del_listado():
        sentencias = []

        def espia(conn, cursor, statement, params, context, executemany):
            sentencias.append(statement)

        event.listen(db.engine, "before_cursor_execute", espia)
        try:
            assert client.get("/blog/mis-emprendimientos").status_code == 200
        finally:
            event.remove(db.engine, "before_cursor_execute", espia)
        return len(sentencias)

    for i in range(3):
        crear_post(autor.id, title=f"Emprendimiento {i}")
    con_tres = consultas_del_listado()

    for i in range(3, 6):
        crear_post(autor.id, title=f"Emprendimiento {i}")
    con_seis = consultas_del_listado()

    # Los 6 entran en una sola pagina (POSTS_POR_PAGINA es 9), asi que la
    # comparacion es entre listados completos y no contra una pagina cortada.
    assert app.config["POSTS_POR_PAGINA"] >= 6
    assert con_seis == con_tres


def test_las_metricas_de_mis_emprendimientos_no_se_inflan_entre_si(
    client, crear_usuario, crear_post, login, db
):
    """Reseñas, productos y servicios se cuentan por separado.

    Las tres salen de la misma consulta: si los joins se cruzaran, cada COUNT
    quedaria multiplicado por las filas de las otras dos tablas.
    """
    autor = crear_usuario(username="autor")
    post = crear_post(autor.id)
    for nombre, puntaje in (("ana", 4), ("beto", 5)):
        usuario = crear_usuario(username=nombre)
        db.session.add(Review(post_id=post.id, user_id=usuario.id, rating=puntaje))
    db.session.add(Product(post_id=post.id, nombre="Pan", precio=100))
    db.session.add(Service(post_id=post.id, titulo="Delivery"))
    db.session.commit()

    login(autor.id)
    html = client.get("/blog/mis-emprendimientos").get_data(as_text=True)

    assert "2 reseñas" in html
    assert '<span class="metrica__valor">4.5</span>' in html
    # Un producto y un servicio: el catalogo los suma.
    assert re.search(
        r'metrica__valor">2</span>\s*<span class="metrica__label">en el catálogo',
        html,
    )


# ------------------------------------------------------- galeria de fotos

def _imagen(nombre="foto.png", color="blue"):
    """Un archivo de imagen valido, listo para subir en un multipart."""
    import io

    from PIL import Image
    from werkzeug.datastructures import FileStorage

    buffer = io.BytesIO()
    Image.new("RGB", (10, 10), color).save(buffer, format="PNG")
    buffer.seek(0)
    return FileStorage(stream=buffer, filename=nombre, content_type="image/png")


def test_crear_un_emprendimiento_con_galeria(client, db, crear_usuario, login):
    autor = crear_usuario(username="autor")
    login(autor.id)

    client.post("/blog/create", data={
        "title": "Panadería", "body": "Pan artesanal", "category": "alimentos",
        "image": _imagen("principal.png"),
        "galeria": [_imagen("uno.png"), _imagen("dos.png")],
    }, content_type="multipart/form-data")

    post = Post.query.filter_by(title="Panadería").first()
    assert post is not None
    assert post.image is not None
    assert len(post.imagenes) == 2
    # La principal va primero y despues las de la galeria.
    assert len(post.galeria) == 3
    assert post.galeria[0] == post.image


def test_no_se_pueden_subir_mas_de_cinco_fotos(client, db, crear_usuario, login):
    autor = crear_usuario(username="autor")
    login(autor.id)

    client.post("/blog/create", data={
        "title": "Demasiadas", "body": "Descripción", "category": "otros",
        "image": _imagen("principal.png"),
        "galeria": [_imagen(f"f{i}.png") for i in range(5)],  # 1 + 5 = 6
    }, content_type="multipart/form-data")

    assert Post.query.filter_by(title="Demasiadas").first() is None


def test_las_fotos_que_ya_estaban_cuentan_para_el_limite(client, db, crear_usuario, crear_post, login):
    from app.blog.modelo_imagen import PostImage

    autor = crear_usuario(username="autor")
    post = crear_post(autor.id, title="Panadería")
    post.image = "principal.png"
    for i in range(3):
        post.imagenes.append(PostImage(filename=f"vieja{i}.png", posicion=i))
    db.session.commit()
    login(autor.id)

    # Ya tiene 4 (principal + 3): subir 2 mas se pasaria de 5.
    client.post(f"/blog/update/{post.id}", data={
        "title": "Panadería", "body": "Pan", "category": "alimentos",
        "galeria": [_imagen("nueva1.png"), _imagen("nueva2.png")],
    }, content_type="multipart/form-data")

    db.session.refresh(post)
    assert len(post.imagenes) == 3  # no se agrego ninguna

    # Una sola si entra.
    client.post(f"/blog/update/{post.id}", data={
        "title": "Panadería", "body": "Pan", "category": "alimentos",
        "galeria": [_imagen("nueva1.png")],
    }, content_type="multipart/form-data")

    db.session.refresh(post)
    assert len(post.imagenes) == 4


def test_el_detalle_muestra_todas_las_fotos(client, db, crear_usuario, crear_post):
    from app.blog.modelo_imagen import PostImage

    autor = crear_usuario(username="autor")
    post = crear_post(autor.id, title="Panadería")
    post.image = "principal.png"
    post.imagenes.append(PostImage(filename="segunda.png", posicion=1))
    db.session.commit()

    html = client.get(f"/blog/{post.id}").get_data(as_text=True)

    assert "uploads/principal.png" in html
    assert "uploads/segunda.png" in html


def test_borrar_un_emprendimiento_borra_sus_fotos(client, db, crear_usuario, crear_post, login):
    """El bug de FK RESTRICT que ya aparecio en reports, favorites y messages."""
    from app.blog.modelo_imagen import PostImage

    autor = crear_usuario(username="autor")
    post = crear_post(autor.id)
    post.imagenes.append(PostImage(filename="foto.png", posicion=0))
    db.session.commit()
    post_id = post.id
    login(autor.id)

    respuesta = client.post(f"/blog/delete/{post_id}")

    assert respuesta.status_code in (200, 302)
    assert Post.query.get(post_id) is None
    assert PostImage.query.filter_by(post_id=post_id).count() == 0


def _archivo_roto(nombre="roto.png"):
    """Pasa el filtro de extension pero no es una imagen: Pillow lo rechaza."""
    import io

    from werkzeug.datastructures import FileStorage

    return FileStorage(
        stream=io.BytesIO(b"esto no es una imagen"),
        filename=nombre,
        content_type="image/png",
    )


def _archivos_en_uploads(app):
    """Los archivos que hay en la carpeta de uploads QUE USA LA APP.

    La ruta sale de la config y no se recalcula a mano: si el test mira un
    directorio y la app escribe en otro, los asserts de huerfanas comparan un
    directorio vacio contra si mismo y pasan sin probar nada. Es lo que pasaba
    cuando esto armaba os.path.join(app.root_path, "static", "uploads"), que
    coincidia con la carpeta real solo mientras nadie moviera nada ni definiera
    UPLOAD_FOLDER.
    """
    import os

    carpeta = app.config["UPLOAD_FOLDER"]
    os.makedirs(carpeta, exist_ok=True)
    return {n for n in os.listdir(carpeta) if os.path.isfile(os.path.join(carpeta, n))}


def test_una_foto_invalida_no_deja_huerfanas_las_anteriores(
    client, db, app, crear_usuario, login
):
    """Si la tercera foto falla, las dos primeras ya se escribieron a disco. Sin
    limpiarlas quedan ahi para siempre: el rollback solo deshace la base."""
    autor = crear_usuario(username="autor")
    login(autor.id)
    antes = _archivos_en_uploads(app)

    client.post("/blog/create", data={
        "title": "Con una rota", "body": "Descripción", "category": "otros",
        "image": _imagen("principal.png"),
        "galeria": [_imagen("uno.png"), _imagen("dos.png"), _archivo_roto(), _imagen("cuatro.png")],
    }, content_type="multipart/form-data")

    assert Post.query.filter_by(title="Con una rota").first() is None
    assert _archivos_en_uploads(app) == antes


def test_una_foto_invalida_al_editar_tampoco_deja_huerfanas(
    client, db, app, crear_usuario, crear_post, login
):
    autor = crear_usuario(username="autor")
    post = crear_post(autor.id, title="Panadería")
    login(autor.id)
    antes = _archivos_en_uploads(app)

    client.post(f"/blog/update/{post.id}", data={
        "title": "Panadería", "body": "Pan", "category": "alimentos",
        "image": _imagen("nueva_principal.png"),
        "galeria": [_imagen("uno.png"), _archivo_roto()],
    }, content_type="multipart/form-data")

    db.session.refresh(post)
    assert post.imagenes == []
    assert post.image is None  # no se guardo la principal nueva
    assert _archivos_en_uploads(app) == antes


def test_una_galeria_valida_si_deja_los_archivos(client, db, app, crear_usuario, login):
    """El contrapeso del test de arriba: no hay que borrar de mas."""
    autor = crear_usuario(username="autor")
    login(autor.id)
    antes = _archivos_en_uploads(app)

    client.post("/blog/create", data={
        "title": "Todas buenas", "body": "Descripción", "category": "otros",
        "image": _imagen("principal.png"),
        "galeria": [_imagen("uno.png"), _imagen("dos.png")],
    }, content_type="multipart/form-data")

    post = Post.query.filter_by(title="Todas buenas").first()
    assert post is not None
    nuevos = _archivos_en_uploads(app) - antes
    assert len(nuevos) == 3
    assert post.image in nuevos
    for imagen in post.imagenes:
        assert imagen.filename in nuevos


def test_borrar_un_usuario_borra_sus_emprendimientos_y_lo_que_cuelga(
    db, crear_usuario, crear_post
):
    """Borrar un User tiene que llevarse sus posts y todo lo que depende de ellos.

    Antes fallaba con IntegrityError: el ORM intentaba dejar los posts
    huerfanos con un UPDATE posts SET author=NULL y la columna es NOT NULL.
    Ahora la FK tiene ON DELETE CASCADE y la relacion, delete-orphan.
    """
    import datetime

    from models.event import Event
    from app.blog.modelo_favorito import Favorite
    from app.blog.modelo_imagen import PostImage

    autor = crear_usuario(username="autor")
    cliente = crear_usuario(username="cliente")
    post = crear_post(autor.id)
    # Cada cosa que cuelga de un emprendimiento, para que ninguna quede suelta.
    db.session.add_all([
        Review(post_id=post.id, user_id=cliente.id, rating=5, comment="Muy bueno"),
        PostImage(post_id=post.id, filename="foto.png", posicion=0),
        Event(post_id=post.id, titulo="Feria", fecha=datetime.date(2026, 9, 1)),
        Favorite(user_id=cliente.id, post_id=post.id),
    ])
    db.session.commit()
    post_id = post.id

    db.session.delete(autor)
    db.session.commit()

    assert Post.query.get(post_id) is None
    assert Review.query.filter_by(post_id=post_id).count() == 0
    assert PostImage.query.filter_by(post_id=post_id).count() == 0
    assert Event.query.filter_by(post_id=post_id).count() == 0
    assert Favorite.query.filter_by(post_id=post_id).count() == 0
    # El otro usuario no se toca: solo se va lo que colgaba del que se borro.
    assert User.query.get(cliente.id) is not None

# --- formulario compartido por el alta y la edicion

def test_el_alta_y_la_edicion_usan_el_mismo_formulario(
    client, crear_usuario, crear_post, login
):
    """Las dos pantallas incluyen el mismo parcial, asi que traen las mismas piezas.

    Es lo que evita que se vuelvan a separar en dos copias: si alguien duplica
    una de las dos, este test lo dice.
    """
    autor = crear_usuario(username="autor")
    post = crear_post(autor.id, title="Panadería")
    login(autor.id)

    alta = client.get("/blog/create").get_data(as_text=True)
    edicion = client.get(f"/blog/update/{post.id}").get_data(as_text=True)

    for html in (alta, edicion):
        # Los tres tramos, los campos reales y el checklist.
        assert 'id="tramo-basico"' in html
        assert 'id="tramo-fotos"' in html
        assert 'id="tramo-ubicacion"' in html
        assert 'name="title"' in html
        assert 'name="body"' in html
        assert 'name="category"' in html
        assert 'name="galeria"' in html
        assert "Qué te falta" in html

    assert "Publicar emprendimiento" in alta
    assert "Guardar cambios" in edicion


def test_la_edicion_trae_los_valores_del_post(
    client, crear_usuario, crear_post, login
):
    autor = crear_usuario(username="autor")
    post = crear_post(
        autor.id, title="Panadería La Espiga", body="Pan de masa madre.",
        category=Categorias.ALIMENTOS,
    )
    login(autor.id)

    html = client.get(f"/blog/update/{post.id}").get_data(as_text=True)

    assert "Panadería La Espiga" in html
    assert "Pan de masa madre." in html

    # El chip tildado tiene que ser el de la categoria guardada, y solo ese.
    tildados = re.findall(r'value="([^"]+)"[^>]*\bchecked\b', html)
    assert tildados == [Categorias.ALIMENTOS]


def test_la_categoria_viaja_como_radio_y_no_como_select(
    client, crear_usuario, login
):
    """Los chips del rediseño son radios de verdad: la eleccion va en el POST.

    Si alguien los vuelve a maquetar como <span> sin input, el formulario
    guardaria siempre la categoria por defecto sin fallar en ningun lado.
    """
    autor = crear_usuario(username="autor")
    login(autor.id)

    html = client.get("/blog/create").get_data(as_text=True)

    assert '<select id="category"' not in html
    assert 'type="radio" name="category"' in html


def test_el_checklist_del_alta_esta_todo_sin_tildar(client, crear_usuario, login):
    """En el alta no hay nada cargado todavia, asi que no puede decir lo contrario."""
    autor = crear_usuario(username="autor")
    login(autor.id)

    html = client.get("/blog/create").get_data(as_text=True)

    assert "0 de 6" in html


def test_el_checklist_de_la_edicion_cuenta_lo_que_el_post_tiene(
    client, db, crear_usuario, crear_post, login
):
    autor = crear_usuario(username="autor")
    post = crear_post(
        autor.id,
        title="Panadería",
        body="x" * reglas.DESCRIPCION_COMPLETA,
        category=Categorias.ALIMENTOS,
    )
    post.address_street = "Av. San Martín 1240"
    db.session.commit()
    login(autor.id)

    html = client.get(f"/blog/update/{post.id}").get_data(as_text=True)

    # Nombre y categoria, descripcion larga y direccion: tres de seis.
    # Faltan la foto principal, las dos de galeria y los horarios.
    assert "3 de 6" in html


def test_el_checklist_no_da_por_cumplida_una_descripcion_corta(
    client, crear_usuario, crear_post, login
):
    autor = crear_usuario(username="autor")
    post = crear_post(autor.id, title="Panadería", body="Corta.")
    login(autor.id)

    html = client.get(f"/blog/update/{post.id}").get_data(as_text=True)

    assert "1 de 6" in html


def test_el_checklist_cuenta_los_horarios_del_usuario(
    client, db, crear_usuario, crear_post, login
):
    """Los horarios cuelgan del usuario, no del emprendimiento.

    Asi que el item puede estar cumplido en un emprendimiento recien creado, si
    el usuario ya los habia cargado antes.
    """
    from app.perfil.modelo_horario import Horario

    autor = crear_usuario(username="autor")
    post = crear_post(autor.id, title="Panadería", body="Corta.")
    db.session.add(Horario(user_id=autor.id, dia_semana=0, cerrado=True))
    db.session.commit()
    login(autor.id)

    html = client.get(f"/blog/update/{post.id}").get_data(as_text=True)

    assert "2 de 6" in html

# --- home: rubros, buscador por cercania y favoritos en la API

def test_el_home_cuenta_los_emprendimientos_de_cada_rubro(
    client, crear_usuario, crear_post
):
    """El "N activos" de cada rubro es real, no decorativo."""
    autor = crear_usuario(username="autor")
    crear_post(autor.id, title="Pan", category=Categorias.ALIMENTOS)
    crear_post(autor.id, title="Facturas", category=Categorias.ALIMENTOS)
    crear_post(autor.id, title="Macetas", category=Categorias.HOGAR)

    html = client.get("/").get_data(as_text=True)

    assert "2 activos" in html
    assert "1 activo" in html
    # Los siete rubros se muestran enteros aunque alguno este en cero: la lista
    # es fija y conteo_por_categoria() no devuelve los vacios.
    assert "0 activos" in html


def test_el_home_no_dice_de_que_ciudad_es_el_total(
    client, crear_usuario, crear_post
):
    """Post no tiene localidad, asi que el contador habla de la plataforma.

    El rediseño muestra "218 emprendimientos en San Rafael"; el "San Rafael" es
    un texto que el diseñador escribio a mano en el editor, no un dato.
    """
    autor = crear_usuario(username="autor")
    crear_post(autor.id, title="Pan")

    html = client.get("/").get_data(as_text=True)

    assert "1 emprendimiento publicado" in html
    assert "San Rafael" not in html


def test_el_home_ofrece_buscar_por_cercania(client):
    """El tercer campo del buscador existe y trae el atajo de ubicacion."""
    html = client.get("/").get_data(as_text=True)

    assert 'id="search-near"' in html
    assert 'id="search-lat"' in html
    assert 'id="search-lon"' in html
    assert "Cerca de mí" in html


def test_el_home_no_promete_un_orden_que_no_existe(client):
    """La grilla trae los ultimos publicados y el titulo lo dice.

    El rediseño propone "Destacados esta semana · los mejor calificados con
    reseñas de los ultimos 30 dias", y esa consulta no existe.
    """
    html = client.get("/").get_data(as_text=True)

    assert "Últimos emprendimientos" in html
    assert "Destacados esta semana" not in html


def test_la_api_no_dice_nada_de_favoritos_sin_sesion(
    client, crear_usuario, crear_post
):
    """Sin login la respuesta es la de siempre: la clave ni siquiera viaja.

    Que no venga es distinto de que venga en False: el que consume tiene que
    poder distinguir "no lo tenes" de "no sabemos quien sos" para decidir si
    dibuja el corazon.
    """
    autor = crear_usuario(username="autor")
    crear_post(autor.id, title="Pan")

    item = client.get("/api/posts/").get_json()["items"][0]

    assert "favorito" not in item


def test_la_api_marca_los_favoritos_del_usuario_logueado(
    client, db, crear_usuario, crear_post, login
):
    from app.blog.modelo_favorito import Favorite

    autor = crear_usuario(username="autor")
    guardado = crear_post(autor.id, title="Guardado")
    suelto = crear_post(autor.id, title="Suelto")

    lector = crear_usuario(username="lector")
    db.session.add(Favorite(user_id=lector.id, post_id=guardado.id))
    db.session.commit()
    login(lector.id)

    items = client.get("/api/posts/").get_json()["items"]
    por_titulo = {i["title"]: i for i in items}

    assert por_titulo["Guardado"]["favorito"] is True
    assert por_titulo["Suelto"]["favorito"] is False


def test_el_token_csrf_esta_disponible_para_el_javascript(client):
    """El corazon de la home es un form POST que arma el JS.

    Sin este meta no tendria de donde sacar el token y el toggle rebotaria con
    un error de CSRF.
    """
    html = client.get("/").get_data(as_text=True)

    assert 'name="csrf-token"' in html

def test_el_listado_no_dice_que_un_emprendimiento_esta_verificado(
    client, crear_usuario, crear_post
):
    """No hay verificacion de un Post, asi que el listado no puede afirmarla.

    El sello estaba puesto sin ningun if y lo llevaban todos. La verificacion
    que existe es de cada Service (Service.verificado, que pone un admin
    despues de mirar la matricula) y se muestra en las pantallas de servicios,
    con su condicion.
    """
    autor = crear_usuario(username="autor")
    crear_post(autor.id, title="Panadería sin verificar")

    html = client.get("/blog/").get_data(as_text=True)

    assert "Panadería sin verificar" in html
    assert "Verificado" not in html


def test_el_detalle_no_dice_que_un_emprendimiento_esta_verificado(
    client, crear_usuario, crear_post
):
    """Mismo criterio que el listado: sin dato de verificacion, sin sello.

    La verificacion que existe es de cada Service (Service.verificado, que
    pone un admin despues de mirar la matricula) y se muestra en las
    pantallas de servicios, con su condicion.
    """
    autor = crear_usuario(username="autor")
    post = crear_post(autor.id, title="Panadería sin verificar")

    html = client.get(f"/blog/{post.id}").get_data(as_text=True)

    assert "Panadería sin verificar" in html
    assert "Verificado" not in html


def test_mis_emprendimientos_no_dice_que_un_emprendimiento_esta_verificado(
    client, crear_usuario, crear_post, login
):
    """El sello tampoco puede afirmarse en la pantalla del propio vendedor."""
    autor = crear_usuario(username="autor")
    crear_post(autor.id, title="Panadería sin verificar")

    login(autor.id)
    html = client.get("/blog/mis-emprendimientos").get_data(as_text=True)

    assert "Panadería sin verificar" in html
    assert "Verificado" not in html


# ------------------------------------------------- filtro "Abierto ahora"

def _abierto_todo_el_dia(user_id):
    """Un horario del dia de hoy (hora argentina) que cubre cualquier momento."""
    from datetime import time as _time

    from app.perfil.modelo_horario import Horario
    from services.horarios import ventana_actual

    hoy, _ayer, _momento = ventana_actual()
    return Horario(
        user_id=user_id, dia_semana=hoy,
        abre=_time(0, 0, 0), cierra=_time(23, 59, 59),
    )


def _cerrado_hoy(user_id):
    from app.perfil.modelo_horario import Horario
    from services.horarios import ventana_actual

    hoy, _ayer, _momento = ventana_actual()
    return Horario(user_id=user_id, dia_semana=hoy, cerrado=True)


def test_abierto_ahora_deja_solo_a_los_que_atienden(
    client, db, crear_usuario, crear_post
):
    """El filtro mira los horarios del autor, no una marca del post.

    Los tres casos que tienen que quedar afuera o adentro son distintos entre
    si: quien atiende, quien tiene el dia marcado cerrado y quien nunca cargo
    horarios. Sin horarios NO es "abierto": seria afirmar algo que no se sabe.
    """
    abierta = crear_usuario(username="abierta")
    cerrada = crear_usuario(username="cerrada")
    sin_datos = crear_usuario(username="sindatos")
    db.session.add_all([_abierto_todo_el_dia(abierta.id), _cerrado_hoy(cerrada.id)])
    db.session.commit()

    crear_post(abierta.id, title="Panadería que atiende")
    crear_post(cerrada.id, title="Panadería con franco")
    crear_post(sin_datos.id, title="Panadería sin horarios")

    html = client.get("/blog/?abierto_ahora=1").get_data(as_text=True)

    assert "Panadería que atiende" in html
    assert "Panadería con franco" not in html
    assert "Panadería sin horarios" not in html


def test_sin_el_parametro_el_listado_no_filtra_por_horario(
    client, db, crear_usuario, crear_post
):
    """Un checkbox sin marcar no viaja: el listado tiene que verse entero."""
    cerrada = crear_usuario(username="cerrada")
    db.session.add(_cerrado_hoy(cerrada.id))
    db.session.commit()
    crear_post(cerrada.id, title="Panadería con franco")

    html = client.get("/blog/").get_data(as_text=True)

    assert "Panadería con franco" in html


def test_abierto_ahora_pinta_su_chip_y_queda_marcado(
    client, db, crear_usuario, crear_post
):
    html = client.get("/blog/?abierto_ahora=1").get_data(as_text=True)

    assert re.search(r'name="abierto_ahora"[^>]*checked', html)
    assert "Quitar el filtro de horario" in html


def test_el_total_cuenta_solo_los_abiertos(client, db, crear_usuario, crear_post):
    """El numero de arriba tiene que ser el de la consulta, no el de todos.

    Es lo que se rompe si el filtro se resuelve en Python despues de paginar:
    el listado muestra uno y el titulo sigue diciendo dos.
    """
    abierta = crear_usuario(username="abierta")
    cerrada = crear_usuario(username="cerrada")
    db.session.add_all([_abierto_todo_el_dia(abierta.id), _cerrado_hoy(cerrada.id)])
    db.session.commit()
    crear_post(abierta.id, title="Panadería que atiende")
    crear_post(cerrada.id, title="Panadería con franco")

    html = client.get("/blog/?abierto_ahora=1").get_data(as_text=True)

    assert re.search(r"1 emprendimiento\s*<", html)
    assert "Panadería con franco" not in html


def test_el_listado_no_consulta_de_mas_por_cada_fila(
    app, client, db, crear_usuario, crear_post
):
    """El costo del listado no puede depender de cuantas filas trae la pagina.

    "Abierto ahora" se resuelve con un EXISTS dentro del WHERE. Si en cambio se
    resolviera iterando las filas y mirando post.author_user.horarios, la
    relacion Horario<-User es lazy="select" y cada emprendimiento agregaria un
    SELECT propio: el N+1 que ya se corrigio en la moderacion y en "Mis
    emprendimientos".

    Se vacia el identity map antes de cada medicion: con los objetos ya
    cargados en la sesion del test, un lazy load no llega a la base y el
    contador daria un falso negativo.
    """
    def contar_consultas(url):
        db.session.expunge_all()
        consultas_vistas = []

        def escuchar(conn, cursor, statement, params, context, many):
            consultas_vistas.append(statement)

        event.listen(db.engine, "before_cursor_execute", escuchar)
        try:
            client.get(url)
        finally:
            event.remove(db.engine, "before_cursor_execute", escuchar)
        return len(consultas_vistas)

    def sumar_posts(desde, hasta):
        for numero in range(desde, hasta):
            autor = crear_usuario(username=f"autor{numero}")
            db.session.add(_abierto_todo_el_dia(autor.id))
            db.session.commit()
            crear_post(autor.id, title=f"Emprendimiento {numero}")

    sumar_posts(0, 3)
    con_tres = contar_consultas("/blog/?abierto_ahora=1")

    sumar_posts(3, 9)
    con_nueve = contar_consultas("/blog/?abierto_ahora=1")

    assert con_nueve == con_tres


# --------------------------------------------- reordenar fotos / principal

def _con_fotos(db, post, *nombres):
    """Le cuelga fotos de galeria al post, en ese orden."""
    from app.blog.modelo_imagen import PostImage

    for posicion, nombre in enumerate(nombres):
        db.session.add(
            PostImage(post_id=post.id, filename=nombre, posicion=posicion)
        )
    db.session.commit()
    return [
        img.id
        for img in PostImage.query.filter_by(post_id=post.id)
        .order_by(PostImage.posicion)
    ]


def test_los_tokens_salen_en_el_mismo_orden_que_la_galeria(db, crear_usuario, crear_post):
    """tokens_de_fotos y post.galeria se recorren juntos: tienen que alinear."""
    autor = crear_usuario(username="autor")
    post = crear_post(autor.id, image="principal.png")
    ids = _con_fotos(db, post, "b.png", "c.png")

    assert reglas.tokens_de_fotos(post) == ["principal", str(ids[0]), str(ids[1])]
    assert post.galeria == ["principal.png", "b.png", "c.png"]


def test_un_orden_que_no_es_permutacion_exacta_se_rechaza(db, crear_usuario, crear_post):
    autor = crear_usuario(username="autor")
    post = crear_post(autor.id, image="principal.png")
    ids = _con_fotos(db, post, "b.png")
    completo = ["principal", str(ids[0])]

    assert reglas.orden_de_fotos_valido(post, completo)
    # Falta una: seria un borrado encubierto.
    assert not reglas.orden_de_fotos_valido(post, ["principal"])
    # Repetida: duplicaria un archivo y perderia el otro.
    assert not reglas.orden_de_fotos_valido(post, ["principal", "principal"])
    # De otro emprendimiento.
    assert not reglas.orden_de_fotos_valido(post, ["principal", "99999"])
    # Vacia.
    assert not reglas.orden_de_fotos_valido(post, [])


def test_reordenar_la_galeria_no_toca_la_principal(client, db, crear_usuario, crear_post, login):
    autor = crear_usuario(username="autor")
    login(autor.id)
    post = crear_post(autor.id, image="principal.png")
    ids = _con_fotos(db, post, "b.png", "c.png")

    client.post(
        f"/blog/{post.id}/fotos/reordenar",
        data={"orden": f"principal,{ids[1]},{ids[0]}"},
    )

    db.session.expire_all()
    assert post.image == "principal.png"
    assert post.galeria == ["principal.png", "c.png", "b.png"]


def test_promover_una_foto_de_la_galeria_intercambia_los_archivos(
    client, db, crear_usuario, crear_post, login
):
    """La principal vieja baja a la galeria: es un swap de strings, no de archivos.

    Lo que se fija es que no se pierda ni se duplique ningun archivo, y que la
    cantidad de filas de post_images no cambie.
    """
    from app.blog.modelo_imagen import PostImage

    autor = crear_usuario(username="autor")
    login(autor.id)
    post = crear_post(autor.id, image="principal.png")
    ids = _con_fotos(db, post, "b.png", "c.png")

    client.post(
        f"/blog/{post.id}/fotos/reordenar",
        data={"orden": f"{ids[1]},principal,{ids[0]}"},
    )

    db.session.expire_all()
    assert post.image == "c.png"
    assert post.galeria == ["c.png", "principal.png", "b.png"]
    # Las mismas tres fotos, ninguna perdida ni repetida.
    assert sorted(post.galeria) == ["b.png", "c.png", "principal.png"]
    # Y las mismas dos filas de siempre: no se creo ni se borro ninguna.
    assert PostImage.query.filter_by(post_id=post.id).count() == 2


def test_un_post_sin_principal_promueve_y_le_sobra_una_fila(
    client, db, crear_usuario, crear_post, login
):
    """Sin Post.image, promover una foto la saca de post_images.

    El total de fotos no cambia, pero una pasa a vivir en Post.image, asi que
    sobra exactamente una fila. El archivo no se toca: pasa a referenciarlo
    Post.image.
    """
    from app.blog.modelo_imagen import PostImage

    autor = crear_usuario(username="autor")
    login(autor.id)
    post = crear_post(autor.id, image=None)
    ids = _con_fotos(db, post, "b.png", "c.png")

    client.post(
        f"/blog/{post.id}/fotos/reordenar",
        data={"orden": f"{ids[1]},{ids[0]}"},
    )

    db.session.expire_all()
    assert post.image == "c.png"
    assert post.galeria == ["c.png", "b.png"]
    assert PostImage.query.filter_by(post_id=post.id).count() == 1


def test_reordenar_las_fotos_de_otro_no_se_puede(
    client, db, crear_usuario, crear_post, login
):
    """El chequeo de dueño, que es lo que esta ruta no puede no tener."""
    autor = crear_usuario(username="autor")
    intruso = crear_usuario(username="intruso")
    post = crear_post(autor.id, image="principal.png")
    ids = _con_fotos(db, post, "b.png")

    login(intruso.id)
    respuesta = client.post(
        f"/blog/{post.id}/fotos/reordenar",
        data={"orden": f"{ids[0]},principal"},
    )

    assert respuesta.status_code == 302
    db.session.expire_all()
    assert post.image == "principal.png"
    assert post.galeria == ["principal.png", "b.png"]


def test_un_orden_invalido_no_aplica_nada(client, db, crear_usuario, crear_post, login):
    """Ni siquiera la parte que cerraba: o entra entero o no entra."""
    autor = crear_usuario(username="autor")
    login(autor.id)
    post = crear_post(autor.id, image="principal.png")
    ids = _con_fotos(db, post, "b.png", "c.png")

    # Sobra una foto ajena, aunque el resto sea una reordenacion legitima.
    client.post(
        f"/blog/{post.id}/fotos/reordenar",
        data={"orden": f"{ids[1]},principal,{ids[0]},99999"},
    )

    db.session.expire_all()
    assert post.galeria == ["principal.png", "b.png", "c.png"]


def test_reordenar_no_acepta_get(client, crear_usuario, crear_post, login):
    """Un GET con efectos se dispara desde un <img src> ajeno."""
    autor = crear_usuario(username="autor")
    login(autor.id)
    post = crear_post(autor.id, image="principal.png")

    assert client.get(f"/blog/{post.id}/fotos/reordenar").status_code == 405


# ------------------------------------ la pantalla de edicion: mover fotos

def test_la_edicion_dibuja_el_formulario_de_reordenar(
    client, db, crear_usuario, crear_post, login
):
    autor = crear_usuario(username="autor")
    login(autor.id)
    post = crear_post(autor.id, image="principal.png")
    _con_fotos(db, post, "b.png")

    html = client.get(f"/blog/update/{post.id}").get_data(as_text=True)

    assert f'action="/blog/{post.id}/fotos/reordenar"' in html
    assert 'id="form-reordenar"' in html


def test_el_formulario_de_reordenar_no_queda_anidado_en_el_grande(
    client, db, crear_usuario, crear_post, login
):
    """Un <form> dentro de otro no es HTML valido: el navegador cierra el
    primero al abrir el segundo y pierde el resto de los campos.

    Se chequea contando: entre el <form> del alta/edicion y el de reordenar hay
    que tener dos aperturas y dos cierres, y el cierre del grande tiene que
    venir ANTES de la apertura del de reordenar.
    """
    autor = crear_usuario(username="autor")
    login(autor.id)
    post = crear_post(autor.id, image="principal.png")
    _con_fotos(db, post, "b.png")

    html = client.get(f"/blog/update/{post.id}").get_data(as_text=True)

    apertura_grande = html.index('class="form-empren__form"')
    apertura_reordenar = html.index('id="form-reordenar"')
    cierre_del_grande = html.index("</form>", apertura_grande)

    assert cierre_del_grande < apertura_reordenar


def test_cada_foto_trae_sus_botones_con_el_orden_ya_calculado(
    client, db, crear_usuario, crear_post, login
):
    """Los botones son submits comunes: andan sin una linea de JavaScript.

    Cada value es el orden COMPLETO que resulta de ese movimiento, asi que la
    ruta recibe lo mismo venga del boton o del arrastre.
    """
    autor = crear_usuario(username="autor")
    login(autor.id)
    post = crear_post(autor.id, image="principal.png")
    ids = _con_fotos(db, post, "b.png", "c.png")

    html = client.get(f"/blog/update/{post.id}").get_data(as_text=True)

    # Subir la segunda (y bajar la principal) dan el mismo orden: b, principal, c.
    assert f'value="{ids[0]},principal,{ids[1]}"' in html
    # Bajar la segunda (y subir la tercera): principal, c, b.
    assert f'value="principal,{ids[1]},{ids[0]}"' in html
    # La ultima se hace principal de una, sin pasar por el medio: c, principal, b.
    assert f'value="{ids[1]},principal,{ids[0]}"' in html
    # Y todos apuntan al form de afuera.
    assert 'form="form-reordenar"' in html


def test_los_botones_que_no_tienen_a_donde_mover_no_se_dibujan(
    client, db, crear_usuario, crear_post, login
):
    """Un control apagado que no hace nada es peor que no tenerlo."""
    autor = crear_usuario(username="autor")
    login(autor.id)
    post = crear_post(autor.id, image="principal.png")
    _con_fotos(db, post, "b.png")

    html = client.get(f"/blog/update/{post.id}").get_data(as_text=True)

    # La primera no puede subir y la ultima no puede bajar: con dos fotos hay
    # una sola flecha de cada lado.
    assert html.count("un lugar antes") == 1
    assert html.count("un lugar después") == 1
    # "Hacer principal" tampoco va en la que ya es principal.
    assert html.count("Hacer principal la foto") == 1


def test_con_una_sola_foto_no_hay_nada_que_reordenar(
    client, crear_usuario, crear_post, login
):
    autor = crear_usuario(username="autor")
    login(autor.id)
    post = crear_post(autor.id, image="principal.png")

    html = client.get(f"/blog/update/{post.id}").get_data(as_text=True)

    assert 'id="form-reordenar"' not in html
    assert 'form="form-reordenar"' not in html


def test_el_alta_no_dibuja_controles_de_reordenar(client, crear_usuario, login):
    """En el alta todavia no hay fotos, asi que no hay nada que mover."""
    autor = crear_usuario(username="autor")
    login(autor.id)

    html = client.get("/blog/create").get_data(as_text=True)

    assert 'id="form-reordenar"' not in html
    assert "Hacer principal" not in html


def test_ya_no_se_avisa_que_no_se_puede_reordenar(
    client, db, crear_usuario, crear_post, login
):
    """El aviso decia la verdad hasta esta tanda; ahora seria falso."""
    autor = crear_usuario(username="autor")
    login(autor.id)
    post = crear_post(autor.id, image="principal.png")
    _con_fotos(db, post, "b.png")

    html = client.get(f"/blog/update/{post.id}").get_data(as_text=True)

    assert "Todavía no se pueden reordenar" not in html
    assert "el orden es el de carga" not in html


def test_el_arrastre_es_un_agregado_y_no_el_unico_camino(
    client, db, crear_usuario, crear_post, login
):
    """fotos.js se carga, pero los botones estan en el HTML sin depender de el."""
    autor = crear_usuario(username="autor")
    login(autor.id)
    post = crear_post(autor.id, image="principal.png")
    _con_fotos(db, post, "b.png")

    html = client.get(f"/blog/update/{post.id}").get_data(as_text=True)

    assert "js/fotos.js" in html
    # Los submits ya vienen servidos, no los crea el script.
    assert 'form="form-reordenar"' in html
    assert "un lugar antes" in html
