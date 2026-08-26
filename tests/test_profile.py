"""Tests del perfil del emprendedor: contacto, avatar y sus emprendimientos."""

import io
import re

from PIL import Image
from werkzeug.datastructures import FileStorage

from app.blog.modelo_favorito import Favorite
from app.blog.modelo_resenia import Review
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

    html = client.get(f"/perfil/{usuario.slug}").get_data(as_text=True)

    assert "5492615551234" in html


def test_el_perfil_renderiza_la_bio_con_formato(client, db, crear_usuario):
    usuario = crear_usuario(username="tomy")
    usuario.biography = "Somos **artesanales** desde 1990.\nVisitanos!"
    db.session.commit()

    html = client.get(f"/perfil/{usuario.slug}").get_data(as_text=True)

    assert "<strong>artesanales</strong>" in html
    assert "1990.<br>Visitanos" in html


def test_el_perfil_no_ejecuta_html_inyectado_en_la_bio(client, db, crear_usuario):
    usuario = crear_usuario(username="tomy")
    usuario.biography = "<script>alert('xss')</script>"
    db.session.commit()

    html = client.get(f"/perfil/{usuario.slug}").get_data(as_text=True)

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

    html = client.get(f"/perfil/{usuario.slug}").get_data(as_text=True)

    assert "uploads/covers/portada_de_prueba.png" in html


def test_el_perfil_muestra_sus_emprendimientos_con_calificacion(
    client, db, crear_usuario, crear_post
):
    autor = crear_usuario(username="autor")
    cliente = crear_usuario(username="cliente")
    post = crear_post(autor.id, title="Panadería del barrio")
    db.session.add(Review(post_id=post.id, user_id=cliente.id, rating=5))
    db.session.commit()

    html = client.get(f"/perfil/{autor.slug}").get_data(as_text=True)

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
    html = client.get(f"/perfil/{autor.slug}").get_data(as_text=True)

    assert "1 vista" in html


def test_un_visitante_no_ve_las_vistas_en_el_perfil_ajeno(
    client, db, crear_usuario, crear_post
):
    """La metrica es para el dueño, no un dato publico."""
    autor = crear_usuario(username="autor")
    crear_post(autor.id)

    html = client.get(f"/perfil/{autor.slug}").get_data(as_text=True)

    assert "vista" not in html


# --------------------------------------------------- estadisticas propias

def test_el_dueño_ve_sus_estadisticas_acumuladas(
    client, db, crear_usuario, crear_post, login
):
    autor = crear_usuario(username="autor")
    cliente = crear_usuario(username="cliente")
    post1 = crear_post(autor.id, title="Panadería")
    post2 = crear_post(autor.id, title="Verdulería")
    post1.views_count = 7
    post2.views_count = 3
    db.session.add(Favorite(user_id=cliente.id, post_id=post1.id))
    db.session.add(Review(post_id=post1.id, user_id=cliente.id, rating=5))
    db.session.add(Review(post_id=post2.id, user_id=cliente.id, rating=4))
    db.session.commit()

    login(autor.id)
    html = client.get(f"/perfil/{autor.slug}").get_data(as_text=True)

    # El titulo del panel cambio con el rediseño ("Tus estadisticas" ->
    # "Tus numeros"), junto con la etiqueta de privado.
    assert "Tus números" in html
    assert "Solo lo ves vos" in html
    assert "10" in html  # 7 + 3 vistas
    assert "4.5" in html  # promedio general


def test_las_estadisticas_solo_cuentan_los_emprendimientos_propios(
    client, db, crear_usuario, crear_post, login
):
    autor = crear_usuario(username="autor")
    otro_autor = crear_usuario(username="otro_autor")
    cliente = crear_usuario(username="cliente")
    propio = crear_post(autor.id, title="Mi negocio")
    ajeno = crear_post(otro_autor.id, title="Negocio ajeno")
    propio.views_count = 2
    ajeno.views_count = 100
    db.session.add(Favorite(user_id=cliente.id, post_id=ajeno.id))
    db.session.add(Review(post_id=ajeno.id, user_id=cliente.id, rating=1))
    db.session.commit()

    login(autor.id)
    html = client.get(f"/perfil/{autor.slug}").get_data(as_text=True)

    assert "100" not in html
    assert "Sin reseñas todavía" in html


def test_un_visitante_no_ve_las_estadisticas_del_perfil_ajeno(
    client, db, crear_usuario, crear_post, login
):
    """Mismo criterio de privacidad que views_count: son datos del dueño."""
    autor = crear_usuario(username="autor")
    visitante = crear_usuario(username="visitante")
    post = crear_post(autor.id)
    post.views_count = 42
    db.session.commit()

    login(visitante.id)
    html = client.get(f"/perfil/{autor.slug}").get_data(as_text=True)

    assert "estadísticas" not in html
    assert "42" not in html


def test_las_estadisticas_no_rompen_sin_emprendimientos(
    client, crear_usuario, login
):
    usuario = crear_usuario(username="tomy")
    login(usuario.id)

    respuesta = client.get(f"/perfil/{usuario.slug}")

    assert respuesta.status_code == 200
    assert "Sin reseñas todavía" in respuesta.get_data(as_text=True)


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

    html = client.get(f"/perfil/{autor.slug}/resenias").get_data(as_text=True)

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

    html = client.get(f"/perfil/{autor.slug}/resenias").get_data(as_text=True)

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

    html = client.get(f"/perfil/{autor.slug}/resenias").get_data(as_text=True)

    assert "Gracias por tu compra" in html


def test_el_historial_se_pagina(client, db, app, crear_usuario, crear_post):
    autor = crear_usuario(username="autor")
    por_pagina = app.config["POSTS_POR_PAGINA"]
    post = crear_post(autor.id)

    for numero in range(por_pagina + 2):
        cliente = crear_usuario(username=f"cliente{numero}")
        db.session.add(Review(post_id=post.id, user_id=cliente.id, rating=3, comment=f"Reseña {numero}"))
    db.session.commit()

    primera = client.get(f"/perfil/{autor.slug}/resenias").get_data(as_text=True)
    segunda = client.get(f"/perfil/{autor.slug}/resenias?page=2").get_data(as_text=True)

    assert primera.count("review-card") > 0
    assert "Página 2" in segunda


def test_el_perfil_linkea_al_historial_de_reseñas(client, crear_usuario, crear_post):
    autor = crear_usuario(username="autor")
    crear_post(autor.id)

    html = client.get(f"/perfil/{autor.slug}").get_data(as_text=True)

    assert f'/perfil/{autor.slug}/resenias' in html


# --------------------------------------------------- slug de usuario

def test_el_slug_se_genera_normalizando_el_username(crear_usuario):
    usuario = crear_usuario(username="Panadería Del Barrio")

    assert usuario.slug == "panaderia-del-barrio"


def test_dos_usernames_que_dan_el_mismo_slug_no_colisionan(crear_usuario):
    primero = crear_usuario(username="Pan Casero")
    segundo = crear_usuario(username="pan casero", email="otro@test.com")

    assert primero.slug == "pan-casero"
    assert segundo.slug == "pan-casero-2"


def test_un_username_largo_no_pasa_el_largo_de_la_columna(crear_usuario):
    from services.slugs import LARGO_MAXIMO_SLUG

    usuario = crear_usuario(username="a" * 80)

    assert len(usuario.slug) == LARGO_MAXIMO_SLUG


def test_dos_usernames_largos_e_iguales_no_terminan_con_el_mismo_slug(crear_usuario):
    """Recortar despues de pegar el sufijo se comeria el "-2", que es lo unico
    que los diferencia."""
    from services.slugs import LARGO_MAXIMO_SLUG

    primero = crear_usuario(username="b" * 80, email="uno@test.com")
    segundo = crear_usuario(username="B" * 80, email="dos@test.com")

    assert primero.slug != segundo.slug
    assert segundo.slug.endswith("-2")
    assert len(segundo.slug) <= LARGO_MAXIMO_SLUG


def test_el_slug_recortado_no_queda_con_un_guion_colgando(crear_usuario):
    usuario = crear_usuario(username=("c" * 59) + " palabra")

    assert not usuario.slug.endswith("-")


def test_un_username_reservado_no_se_queda_con_la_ruta(client, crear_usuario):
    """"edit" es una ruta real bajo /perfil/ y le gana a /perfil/<slug>."""
    usuario = crear_usuario(username="edit")

    assert usuario.slug == "edit-2"

    # Y la ruta estatica sigue siendo la de edicion, no el perfil de nadie.
    assert client.get("/perfil/edit").status_code in (302, 200)
    assert client.get("/perfil/edit-2").status_code == 200


def test_toda_ruta_estatica_bajo_perfil_esta_reservada(app):
    """Recorre el url_map real en vez de una lista escrita a mano.

    Werkzeug le da prioridad a una ruta estatica sobre /perfil/<slug>, asi que
    cada vez que se agrega una ruta bajo /perfil/ hay que reservar ese nombre o
    el usuario que se llame igual queda con el perfil inaccesible. Ya se olvido
    dos veces (create_bio en la Tanda A, horarios en b284be4), y las dos veces
    se descubrio a mano: esto lo convierte en un test que falla solo.
    """
    from services.slugs import SLUGS_RESERVADOS

    prefijo = "/perfil/"
    faltantes = {}
    for regla in app.url_map.iter_rules():
        if not regla.rule.startswith(prefijo):
            continue
        primer_segmento = regla.rule[len(prefijo):].split("/")[0]
        # "<slug>" y "<int:user_id>" son la ruta del perfil en si, no colisionan.
        if primer_segmento.startswith("<") or not primer_segmento:
            continue
        if primer_segmento not in SLUGS_RESERVADOS:
            faltantes[primer_segmento] = regla.endpoint

    assert not faltantes, (
        "Hay rutas bajo /perfil/ cuyo nombre no esta en SLUGS_RESERVADOS "
        f"(services/slugs.py): {faltantes}. Un usuario con ese slug quedaria "
        "sin perfil, porque la ruta estatica le gana."
    )


def test_los_slugs_reservados_no_se_asignan(crear_usuario):
    from services.slugs import SLUGS_RESERVADOS

    for reservado in ("admin", "api", "static", "login", "logout", "perfil", "create_bio"):
        assert reservado in SLUGS_RESERVADOS

    usuario = crear_usuario(username="Admin", email="admin@test.com")
    assert usuario.slug == "admin-2"


def test_un_slug_normal_no_se_ve_afectado_por_la_lista(crear_usuario):
    usuario = crear_usuario(username="editorial")

    assert usuario.slug == "editorial"


def test_el_perfil_responde_por_slug(client, crear_usuario):
    usuario = crear_usuario(username="Tomy")

    respuesta = client.get("/perfil/tomy")

    assert respuesta.status_code == 200
    assert "Tomy" in respuesta.get_data(as_text=True)


def test_el_perfil_por_id_redirige_301_al_slug(client, crear_usuario):
    usuario = crear_usuario(username="Tomy")

    respuesta = client.get(f"/perfil/{usuario.id}")

    assert respuesta.status_code == 301
    # URL completa y no endswith(): con endswith, un destino incorrecto que
    # igual termine en "/perfil/tomy" pasaria el test sin que nadie se entere.
    assert respuesta.headers["Location"] == "/perfil/tomy"


def test_el_historial_por_id_redirige_301_al_slug(client, crear_usuario):
    usuario = crear_usuario(username="Tomy")

    respuesta = client.get(f"/perfil/{usuario.id}/resenias")

    assert respuesta.status_code == 301
    assert respuesta.headers["Location"] == "/perfil/tomy/resenias"


def test_el_redirect_al_slug_conserva_el_query_string(client, crear_usuario):
    """Sin esto, /perfil/5/resenias?page=2 caia siempre en la pagina 1."""
    usuario = crear_usuario(username="Tomy")

    respuesta = client.get(f"/perfil/{usuario.id}/resenias?page=2")

    assert respuesta.status_code == 301
    assert respuesta.headers["Location"] == "/perfil/tomy/resenias?page=2"


def test_el_redirect_del_perfil_tambien_conserva_el_query_string(client, crear_usuario):
    usuario = crear_usuario(username="Tomy")

    respuesta = client.get(f"/perfil/{usuario.id}?utm_source=whatsapp")

    assert respuesta.status_code == 301
    assert respuesta.headers["Location"] == "/perfil/tomy?utm_source=whatsapp"


# --------------------------------------------------- ubicacion textual

def test_editar_perfil_guarda_la_ubicacion_textual(client, db, crear_usuario, login):
    usuario = crear_usuario(username="tomy")
    login(usuario.id)

    client.post("/perfil/edit", data={
        "biography": "Bio", "location": "Maipú, Mendoza", "address_street": "",
    })

    db.session.refresh(usuario)
    assert usuario.location == "Maipú, Mendoza"


def test_la_ubicacion_textual_no_se_geocodifica(client, db, crear_usuario, login, monkeypatch):
    """Es texto libre: no toca address_street ni las coordenadas del mapa."""
    from app.perfil import vistas

    def _explotar(*args, **kwargs):
        raise AssertionError("no se debe geocodificar la ubicación textual")

    monkeypatch.setattr(vistas, "get_coordinates_from_address", _explotar)

    usuario = crear_usuario(username="tomy")
    login(usuario.id)

    client.post("/perfil/edit", data={
        "biography": "Bio", "location": "Maipú, Mendoza", "address_street": "",
    })

    db.session.refresh(usuario)
    assert usuario.location == "Maipú, Mendoza"
    assert usuario.address_street is None
    assert usuario.latitude is None
    assert usuario.longitude is None


def test_la_ubicacion_textual_y_la_direccion_del_mapa_conviven(
    client, db, crear_usuario, login, monkeypatch
):
    from app.perfil import vistas

    monkeypatch.setattr(
        vistas, "get_coordinates_from_address", lambda *a, **k: (-32.9, -68.8)
    )

    usuario = crear_usuario(username="tomy")
    login(usuario.id)

    client.post("/perfil/edit", data={
        "biography": "Bio",
        "location": "Maipú, Mendoza",
        "address_street": "Av. San Martín 123, Maipú, Mendoza",
    })

    db.session.refresh(usuario)
    assert usuario.location == "Maipú, Mendoza"
    assert usuario.address_street == "Av. San Martín 123, Maipú, Mendoza"
    assert usuario.latitude == -32.9


def test_el_perfil_publico_muestra_la_ubicacion_textual(client, db, crear_usuario):
    usuario = crear_usuario(username="tomy")
    usuario.location = "Maipú, Mendoza"
    db.session.commit()

    html = client.get("/perfil/tomy").get_data(as_text=True)

    assert "Maipú, Mendoza" in html


def test_la_ubicacion_textual_sola_no_dibuja_el_mapa(client, db, crear_usuario):
    """El mapa cuelga de address_street/coordenadas, no de location."""
    usuario = crear_usuario(username="tomy")
    usuario.location = "Maipú, Mendoza"
    db.session.commit()

    html = client.get("/perfil/tomy").get_data(as_text=True)

    assert "Maipú, Mendoza" in html
    assert "new maplibregl.Map" not in html


# --------------------------------------------------- compartir perfil

def test_el_perfil_trae_el_boton_de_compartir_apuntando_al_perfil(
    client, crear_usuario
):
    usuario = crear_usuario(username="Tomy")

    html = client.get("/perfil/tomy").get_data(as_text=True)

    assert "share-btn" in html
    assert 'data-share-url="http://localhost/perfil/tomy"' in html
    assert "Perfil de Tomy" in html


def test_compartir_un_emprendimiento_sigue_apuntando_al_post(
    client, crear_usuario, crear_post
):
    """El partial quedo parametrizado, pero su default no tiene que cambiar."""
    autor = crear_usuario(username="autor")
    post = crear_post(autor.id, title="Panadería")

    html = client.get(f"/blog/{post.id}").get_data(as_text=True)

    assert f'data-share-url="http://localhost/blog/{post.id}"' in html


def test_un_slug_inexistente_da_404(client):
    assert client.get("/perfil/no-existe").status_code == 404


def test_un_id_inexistente_da_404(client):
    assert client.get("/perfil/999999").status_code == 404


# --------------------------------------------------- menu de cuenta

def test_las_pantallas_de_cuenta_marcan_su_item_en_el_menu(
    client, crear_usuario, login
):
    """El parcial del menu sabe marcar el item activo desde el rediseño, pero
    ninguna de las tres pantallas le pasaba `seccion`, asi que la marca no se
    dibujaba nunca: ni la clase ni el aria-current llegaban al HTML.

    Se chequea el HTML renderizado y no el include, que es justamente lo que
    dejaba pasar el error: el `{% if etiqueta == seccion %}` con `seccion`
    indefinido no falla, da falso y sigue de largo.
    """
    usuario = crear_usuario(username="tomy")
    login(usuario.id)

    pantallas = (
        ("/blog/mis-emprendimientos", "Mis emprendimientos"),
        ("/perfil/tomy/resenias", "Reseñas recibidas"),
        ("/perfil/edit", "Ajustes"),
    )

    # Los siete items del menu, activo o no. Ajustes ademas tiene sus propias
    # solapas con aria-current, asi que contar aria-current sobre la pagina
    # entera daria dos y no diria nada del menu.
    items = re.compile(
        r'<a href="[^"]*"\s+class="cuenta__item([^"]*)"\s*([^>]*)>\s*([^<]+)',
    )

    for ruta, etiqueta in pantallas:
        html = client.get(ruta).get_data(as_text=True)

        encontrados = items.findall(html)
        assert len(encontrados) == 7, (ruta, len(encontrados))

        activos = [
            (clases, atributos, texto.strip())
            for clases, atributos, texto in encontrados
            if "cuenta__item--activo" in clases
        ]
        assert len(activos) == 1, (ruta, activos)

        _clases, atributos, texto = activos[0]
        # El marcado tiene que caer en SU item, no en cualquiera de los siete.
        assert texto == etiqueta, (ruta, texto)
        assert 'aria-current="page"' in atributos, (ruta, atributos)
