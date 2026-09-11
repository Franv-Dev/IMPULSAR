"""Tests del perfil del emprendedor: contacto, avatar y sus emprendimientos."""

import io
import re
from datetime import time, timedelta

from PIL import Image
from werkzeug.datastructures import FileStorage

from app.blog.modelo_favorito import Favorite
from app.blog.modelo_resenia import Review
from app.perfil import formulario, reglas
from app.servicios.modelo import Service
from app.turnos.modelo_turno import EstadosTurno, Turno
from models.user import User
from services.eventos import hoy_en_argentina


def test_editar_perfil_guarda_datos_de_contacto(client, db, crear_usuario, login):
    usuario = crear_usuario(username="tomy")
    login(usuario.id)

    client.post("/perfil/edit/contacto", data={
        "phone": "261 555-1234",
        "whatsapp": "5492615551234",
        "instagram_url": "https://instagram.com/tomy",
        "facebook_url": "https://facebook.com/tomy",
        "twitter_url": "https://twitter.com/tomy",
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

    Las tres pantallas del emprendimiento que estaban aca se fueron al menu del
    panel con la tanda del panel (ver el test de abajo): _menu_cuenta quedo en
    las de "Mi actividad" y ajustes.
    """
    usuario = crear_usuario(username="tomy")
    login(usuario.id)

    pantallas = (
        ("/perfil/edit", "Ajustes"),
        ("/mensajes/", "Mensajes"),
        ("/blog/favoritos", "Favoritos"),
        ("/oportunidades/mias", "Mis oportunidades"),
    )

    # Los nueve items del menu, activo o no. Eran ocho hasta las oportunidades,
    # que sumaron "Mis oportunidades" al hacer su pantalla: va en este menu y no
    # en el del panel porque publicar lo que uno necesita es actividad propia y
    # no trabajo del emprendimiento (eso es "Propuestas enviadas", que si esta
    # en el del panel). Ajustes ademas tiene sus propias
    # solapas con aria-current, asi que contar aria-current sobre la pagina
    # entera daria dos y no diria nada del menu.
    items = re.compile(
        r'<a href="[^"]*"\s+class="cuenta__item([^"]*)"\s*([^>]*)>\s*([^<]+)',
    )

    for ruta, etiqueta in pantallas:
        html = client.get(ruta).get_data(as_text=True)

        encontrados = items.findall(html)
        assert len(encontrados) == 9, (ruta, len(encontrados))

        activos = [
            (clases, atributos, texto.strip())
            for clases, atributos, texto in encontrados
            if "cuenta__item--activo" in clases
        ]
        assert len(activos) == 1, (ruta, activos)

        _clases, atributos, texto = activos[0]
        # El marcado tiene que caer en SU item, no en cualquiera de los nueve.
        assert texto == etiqueta, (ruta, texto)
        assert 'aria-current="page"' in atributos, (ruta, atributos)


# --- formato de los datos de contacto

def test_un_telefono_con_letras_no_se_guarda(client, db, crear_usuario, login):
    """El telefono existe para que alguien lo marque: uno con letras no falla
    en ningun lado, se publica en el perfil y el cliente no llega a nadie."""
    usuario = crear_usuario(username="tomy")
    login(usuario.id)

    respuesta = client.post("/perfil/edit/contacto", data={"phone": "llamame"})

    db.session.refresh(usuario)
    assert respuesta.status_code == 200
    assert usuario.phone is None


def test_un_whatsapp_demasiado_corto_no_se_guarda(client, db, crear_usuario, login):
    usuario = crear_usuario(username="tomy")
    login(usuario.id)

    client.post("/perfil/edit/contacto", data={"whatsapp": "1234"})

    db.session.refresh(usuario)
    assert usuario.whatsapp is None


def test_un_telefono_mal_escrito_no_guarda_el_resto_del_formulario(
    client, db, crear_usuario, login
):
    """Se corta antes de tocar nada: guardar los otros campos y no el telefono
    dejaria el contacto a medio actualizar sin que se note cual falto."""
    usuario = crear_usuario(username="tomy")
    login(usuario.id)

    client.post("/perfil/edit/contacto", data={
        "phone": "llamame",
        "whatsapp": "2611234567",
        "instagram_url": "https://instagram.com/tomy",
    })

    db.session.refresh(usuario)
    assert usuario.whatsapp is None
    assert usuario.instagram_url is None


def test_los_telefonos_con_separadores_se_siguen_guardando(
    client, db, crear_usuario, login
):
    """El control de los anteriores: se acepta el numero como se escribe de
    verdad, y se guarda tal cual, sin normalizar a E.164."""
    usuario = crear_usuario(username="tomy")
    login(usuario.id)

    client.post("/perfil/edit/contacto", data={
        "phone": "+54 9 261 123-4567", "whatsapp": "(261) 4-123456",
    })

    db.session.refresh(usuario)
    assert usuario.phone == "+54 9 261 123-4567"
    assert usuario.whatsapp == "(261) 4-123456"


def test_borrar_el_telefono_sigue_siendo_valido(client, db, crear_usuario, login):
    """Vacio no es un error: los dos campos son opcionales y quien los borra lo
    hace a proposito."""
    usuario = crear_usuario(username="tomy")
    usuario.phone = "2611234567"
    db.session.commit()
    login(usuario.id)

    client.post("/perfil/edit/contacto", data={"phone": ""})

    db.session.refresh(usuario)
    assert usuario.phone is None


def test_un_telefono_mal_escrito_no_borra_lo_que_ya_se_habia_escrito(
    client, crear_usuario, login
):
    """Se repinta con lo que la persona escribio y no con lo que hay guardado.

    Si el formulario vuelve pintado desde user.*, corregir el teléfono cuesta
    reescribir los otros cuatro campos, incluido el WhatsApp que estaba bien.
    Es el mismo patron que ya usa el panel de horarios, que devuelve los
    pendientes y no las filas guardadas.
    """
    usuario = crear_usuario(username="tomy")
    login(usuario.id)

    respuesta = client.post("/perfil/edit/contacto", data={
        "instagram_url": "https://instagram.com/tomy",
        "whatsapp": "2611234567",
        "phone": "llamame",
    })

    html = respuesta.get_data(as_text=True)
    assert "https://instagram.com/tomy" in html
    assert "2611234567" in html
    # Y el que fallo tambien vuelve, para que se vea que hay que corregir.
    assert "llamame" in html


def test_el_formulario_de_edicion_se_precarga_con_lo_guardado(
    client, db, crear_usuario, login
):
    """El control del anterior: al entrar (GET) se sigue viendo lo que hay en
    la base, que es de donde salen los campos cuando no hubo POST."""
    usuario = crear_usuario(username="tomy")
    usuario.location = "Maipú"
    usuario.phone = "2611234567"
    db.session.commit()
    login(usuario.id)

    assert "Maipú" in client.get("/perfil/edit").get_data(as_text=True)
    assert "2611234567" in client.get("/perfil/edit/contacto").get_data(as_text=True)


# ------------------------------------- "Lo que tenes en curso" (turnos y presupuestos)

def _turno_de(db, crear_usuario, crear_post, cliente, cuando,
              estado=EstadosTurno.ACTIVO):
    """Un turno de `cliente` sobre el servicio de otro, en la fecha pedida."""
    vendedor = crear_usuario(username=f"vendedor{cuando.toordinal()}{estado}")
    post = crear_post(author_id=vendedor.id, title="Bicis Mendoza")
    servicio = Service(
        post_id=post.id,
        titulo="Service de bici",
        rubro="otros",
        turnos_habilitados=True,
        duracion_turno_minutos=60,
    )
    db.session.add(servicio)
    db.session.commit()

    turno = Turno(
        service_id=servicio.id,
        cliente_id=cliente.id,
        fecha=cuando,
        hora_inicio=time(10, 0),
        hora_fin=time(11, 0),
        estado=estado,
    )
    db.session.add(turno)
    db.session.commit()
    return turno


def test_el_dueño_ve_sus_turnos_proximos_en_el_perfil(
    client, db, crear_usuario, crear_post, login
):
    """El perfil de quien no vende dejaba de estar vacio: sus turnos y sus
    presupuestos viven en dos pantallas aparte y no asomaban por ningun lado."""
    cliente = crear_usuario(username="camila")
    _turno_de(db, crear_usuario, crear_post, cliente, hoy_en_argentina() + timedelta(days=3))
    login(cliente.id)

    html = client.get(f"/perfil/{cliente.slug}").get_data(as_text=True)

    assert "Lo que tenés en curso" in html
    assert "Service de bici" in html


def test_un_visitante_no_ve_los_turnos_del_perfil_ajeno(
    client, db, crear_usuario, crear_post, login
):
    """Misma privacidad que las estadisticas: la vista ni los calcula cuando
    mira otro, asi que no hay forma de que se filtren por el template."""
    cliente = crear_usuario(username="camila")
    _turno_de(db, crear_usuario, crear_post, cliente, hoy_en_argentina() + timedelta(days=3))
    curioso = crear_usuario(username="curioso")
    login(curioso.id)

    html = client.get(f"/perfil/{cliente.slug}").get_data(as_text=True)

    assert "Lo que tenés en curso" not in html
    assert "Service de bici" not in html


def test_un_turno_que_ya_paso_no_cuenta_como_en_curso(
    client, db, crear_usuario, crear_post, login
):
    """El bloque contesta "que tengo por delante": un turno de la semana pasada
    y uno cancelado no son nada que hacer."""
    cliente = crear_usuario(username="camila")
    _turno_de(db, crear_usuario, crear_post, cliente, hoy_en_argentina() - timedelta(days=2))
    login(cliente.id)

    html = client.get(f"/perfil/{cliente.slug}").get_data(as_text=True)

    assert "Lo que tenés en curso" not in html


def test_un_turno_cancelado_no_cuenta_como_en_curso(
    client, db, crear_usuario, crear_post, login
):
    cliente = crear_usuario(username="camila")
    _turno_de(
        db, crear_usuario, crear_post, cliente,
        hoy_en_argentina() + timedelta(days=3),
        estado=EstadosTurno.CANCELADO,
    )
    login(cliente.id)

    html = client.get(f"/perfil/{cliente.slug}").get_data(as_text=True)

    assert "Lo que tenés en curso" not in html


def test_el_perfil_sin_emprendimientos_invita_a_publicar_uno(
    client, db, crear_usuario, login
):
    """El hueco dicho como propuesta. Solo para el dueño: al visitante no le
    sirve de nada que le ofrezcan publicar en el perfil de otro."""
    cliente = crear_usuario(username="camila")
    login(cliente.id)

    html = client.get(f"/perfil/{cliente.slug}").get_data(as_text=True)

    assert "¿Vos también hacés algo?" in html

    otro = crear_usuario(username="curioso")
    login(otro.id)
    ajeno = client.get(f"/perfil/{cliente.slug}").get_data(as_text=True)

    assert "¿Vos también hacés algo?" not in ajeno


# ------------------------------------- Reseñas en el perfil (pestaña nueva)

def test_las_resenias_recibidas_se_ven_en_el_perfil(
    client, db, crear_usuario, crear_post
):
    """Estaban solo en /perfil/<slug>/resenias: la prueba de que a este
    emprendimiento ya le compraron quedaba a un click, justo cuando el
    visitante esta decidiendo."""
    autor = crear_usuario(username="valentina")
    post = crear_post(author_id=autor.id, title="Panadería del barrio")
    cliente = crear_usuario(username="camila")
    db.session.add(Review(
        post_id=post.id, user_id=cliente.id, rating=5, comment="Excelente pan"
    ))
    db.session.commit()

    html = client.get(f"/perfil/{autor.slug}").get_data(as_text=True)

    assert "Excelente pan" in html
    assert "1 reseña" in html


def test_el_perfil_sin_resenias_no_dibuja_la_pestania(
    client, db, crear_usuario, crear_post
):
    """Un boton sin panel detras queda vivo en la barra y no hace nada: la
    pestaña se dibuja con la misma condicion que su contenido."""
    autor = crear_usuario(username="valentina")
    crear_post(author_id=autor.id, title="Panadería del barrio")

    html = client.get(f"/perfil/{autor.slug}").get_data(as_text=True)

    assert 'data-perfil-tab="resenias"' not in html


def test_el_perfil_muestra_las_ultimas_resenias_y_no_todas(
    client, db, crear_usuario, crear_post
):
    """El perfil es un resumen: la lista completa (paginada) sigue en /resenias."""
    autor = crear_usuario(username="valentina")
    post = crear_post(author_id=autor.id, title="Panadería del barrio")
    for i in range(reglas.MAX_RESENIAS_EN_EL_PERFIL + 2):
        cliente = crear_usuario(username=f"cliente{i}")
        db.session.add(Review(
            post_id=post.id, user_id=cliente.id, rating=5, comment=f"Reseña {i}"
        ))
    db.session.commit()

    html = client.get(f"/perfil/{autor.slug}").get_data(as_text=True)

    assert html.count("review-card__comment") == reglas.MAX_RESENIAS_EN_EL_PERFIL
    # El resumen es sobre TODAS, no sobre las que se dibujan.
    assert "5 reseñas" in html


# ------------------------------------- "Ver como visitante"

def test_el_dueño_ve_la_barra_que_le_dice_que_es_su_perfil(
    client, crear_usuario, login
):
    """La app no decia en ningun lado que estabas parado en tu propio perfil."""
    autor = crear_usuario(username="valentina")
    login(autor.id)

    html = client.get(f"/perfil/{autor.slug}").get_data(as_text=True)

    assert "Este es tu perfil" in html
    assert "Ver como visitante" in html


def test_un_visitante_no_ve_la_barra_del_dueño(client, crear_usuario, login):
    autor = crear_usuario(username="valentina")
    curioso = crear_usuario(username="curioso")
    login(curioso.id)

    html = client.get(f"/perfil/{autor.slug}").get_data(as_text=True)

    assert "Este es tu perfil" not in html
    assert "Ver como visitante" not in html


def test_ver_como_visitante_apaga_de_verdad_lo_privado(
    client, db, crear_usuario, crear_post, login
):
    """No es un dibujo: con ?ver=visitante la vista ni consulta las
    estadisticas ni los turnos, asi que no hay nada privado que filtrar."""
    autor = crear_usuario(username="valentina")
    crear_post(author_id=autor.id, title="Panadería del barrio")
    _turno_de(db, crear_usuario, crear_post, autor,
              hoy_en_argentina() + timedelta(days=3))
    login(autor.id)

    propia = client.get(f"/perfil/{autor.slug}").get_data(as_text=True)
    assert "Tus números" in propia
    assert "Lo que tenés en curso" in propia

    previa = client.get(
        f"/perfil/{autor.slug}?ver=visitante"
    ).get_data(as_text=True)

    assert "Tus números" not in previa
    assert "Lo que tenés en curso" not in previa
    # Pero sigue sabiendo que es suyo, o no tendria como volver.
    assert "Así te ve cualquiera que entre" in previa
    assert "Volver a mi vista" in previa


def test_ver_como_visitante_en_un_perfil_ajeno_no_cambia_nada(
    client, crear_usuario, login
):
    """El parametro es del dueño: pegarlo en el perfil de otro no puede
    encender ninguna barra ni ningun aviso."""
    autor = crear_usuario(username="valentina")
    curioso = crear_usuario(username="curioso")
    login(curioso.id)

    html = client.get(
        f"/perfil/{autor.slug}?ver=visitante"
    ).get_data(as_text=True)

    assert "Así te ve cualquiera que entre" not in html
    assert "Volver a mi vista" not in html


# ------------------------------------- El perfil de un cliente es otra pantalla

def test_el_perfil_de_un_cliente_no_lleva_portada_ni_horarios(
    client, crear_usuario, login
):
    """Compartir template con el emprendedor le dejaba una portada de negocio y
    una grilla de horarios que no va a tener nunca: leia como pantalla rota."""
    cliente = crear_usuario(username="camila", rol="usuario")
    login(cliente.id)

    html = client.get(f"/perfil/{cliente.slug}").get_data(as_text=True)

    assert "perfil-hero--cliente" in html
    assert "perfil-hero__portada" not in html
    assert "Horarios de atención" not in html


def test_un_usuario_con_emprendimientos_conserva_la_forma_de_negocio(
    client, crear_usuario, crear_post, login
):
    """Si un "usuario" publicó algo, el que está mal es el rol: quedarse con la
    forma de negocio es lo que no rompe la pantalla."""
    dueño = crear_usuario(username="camila", rol="usuario")
    crear_post(author_id=dueño.id, title="Tejidos de Camila")
    login(dueño.id)

    html = client.get(f"/perfil/{dueño.slug}").get_data(as_text=True)

    assert "perfil-hero--cliente" not in html
    assert "perfil-hero__portada" in html


# ------------------------------------- Ajustes: las tres pantallas y su previa

def test_las_tres_solapas_de_ajustes_existen_y_se_enlazan(client, crear_usuario, login):
    """Perfil público, contacto y horarios son la misma sección: desde
    cualquiera de las tres se llega a las otras dos."""
    usuario = crear_usuario(username="tomy")
    login(usuario.id)

    for url in ("/perfil/edit", "/perfil/edit/contacto", "/perfil/horarios"):
        html = client.get(url).get_data(as_text=True)
        assert 'href="/perfil/edit"' in html
        assert 'href="/perfil/edit/contacto"' in html
        assert 'href="/perfil/horarios"' in html


def test_la_pantalla_de_perfil_publico_no_edita_el_contacto(
    client, crear_usuario, login
):
    """Los cinco campos se mudaron: dejarlos también acá sería tener dos
    formularios que guardan lo mismo y uno se iba a quedar atrás."""
    usuario = crear_usuario(username="tomy")
    login(usuario.id)

    html = client.get("/perfil/edit").get_data(as_text=True)

    assert 'name="biography"' in html
    assert 'name="phone"' not in html
    assert 'name="instagram_url"' not in html


def test_ajustes_muestra_la_vista_previa_con_lo_guardado(
    client, db, crear_usuario, login
):
    """Editar el perfil era escribir a ciegas: no se veía en ningún lado qué
    estaba cambiando."""
    usuario = crear_usuario(username="tomy")
    usuario.biography = "Tostamos café en Godoy Cruz"
    usuario.location = "Godoy Cruz, Mendoza"
    db.session.commit()
    login(usuario.id)

    html = client.get("/perfil/edit").get_data(as_text=True)

    assert "Así te ven" in html
    assert "Tostamos café en Godoy Cruz" in html
    assert "Godoy Cruz, Mendoza" in html


def test_la_previa_vuelve_con_lo_que_se_escribio_si_algo_falla(
    client, crear_usuario, login
):
    """Se pinta desde `campos` y no desde el usuario: si se pintara de la base,
    al volver por un error mostraría lo viejo y no lo que hay en pantalla."""
    usuario = crear_usuario(username="tomy")
    login(usuario.id)

    html = client.post("/perfil/edit/contacto", data={
        "phone": "llamame", "whatsapp": "2611234567",
    }).get_data(as_text=True)

    assert "Así te ven" in html
    assert "WhatsApp" in html


def test_el_error_del_telefono_se_dibuja_en_el_campo(client, crear_usuario, login):
    """Antes volvía como un aviso suelto arriba de todo y había que adivinar
    cuál de los diez campos lo había producido."""
    usuario = crear_usuario(username="tomy")
    login(usuario.id)

    html = client.post(
        "/perfil/edit/contacto", data={"phone": "llamame"}
    ).get_data(as_text=True)

    assert 'aria-describedby="error-phone"' in html
    assert "ajustes-estado--error" in html


def test_se_puede_quitar_la_foto_y_la_portada(client, db, crear_usuario, login):
    """Se podía cambiar la foto pero no volver a no tener ninguna."""
    usuario = crear_usuario(username="tomy")
    usuario.avatar = "foto.png"
    usuario.cover_image = "portada.png"
    db.session.commit()
    login(usuario.id)

    client.post("/perfil/edit", data={
        "biography": "Hago pan artesanal", "address_street": "",
        "quitar_avatar": "on", "quitar_cover": "on",
    })

    db.session.refresh(usuario)
    assert usuario.avatar is None
    assert usuario.cover_image is None


def test_subir_una_foto_le_gana_a_quitarla(client, db, crear_usuario, login):
    """Si mandó las dos cosas, lo que quiso es la foto nueva."""
    usuario = crear_usuario(username="tomy")
    usuario.avatar = "vieja.png"
    db.session.commit()
    login(usuario.id)

    buffer = io.BytesIO()
    Image.new("RGB", (10, 10), "blue").save(buffer, format="PNG")
    buffer.seek(0)
    nueva = FileStorage(stream=buffer, filename="nueva.png", content_type="image/png")

    client.post(
        "/perfil/edit",
        data={"biography": "Bio", "avatar": nueva, "quitar_avatar": "on"},
        content_type="multipart/form-data",
    )

    db.session.refresh(usuario)
    assert usuario.avatar is not None
    assert usuario.avatar != "vieja.png"


def test_ajustes_dice_si_la_direccion_se_encontro_en_el_mapa(
    client, db, crear_usuario, login
):
    """La geocodificación pasaba en silencio: el aviso aparecía una vez al
    guardar y después no quedaba rastro de si la dirección había entrado."""
    usuario = crear_usuario(username="tomy")
    usuario.address_street = "Güemes 1480, Godoy Cruz"
    db.session.commit()
    login(usuario.id)

    sin_mapa = client.get("/perfil/edit").get_data(as_text=True)
    assert "No la encontramos en el mapa" in sin_mapa

    usuario.latitude, usuario.longitude = -32.9256, -68.8506
    db.session.commit()

    con_mapa = client.get("/perfil/edit").get_data(as_text=True)
    assert "Encontrada en el mapa" in con_mapa


def test_horarios_muestra_el_cartel_que_va_a_encender(
    client, db, crear_usuario, login
):
    """Se cargaban a ciegas: qué cartel encienden recién se veía entrando al
    perfil."""
    usuario = crear_usuario(username="tomy")
    login(usuario.id)

    html = client.get("/perfil/horarios").get_data(as_text=True)

    assert "Así te ven" in html
    assert "Todavía no cargaste horarios" in html


# ------------------------------- Ajustes: una sola lista de campos del perfil

def test_la_tupla_del_perfil_es_la_union_de_las_dos_pantallas():
    """CAMPOS_DEL_PERFIL no es una tercera lista: sale de las otras dos.

    Si vuelve a escribirse a mano, el orden o el contenido se despegan de lo
    que declaran las pantallas y este test lo dice.
    """
    assert formulario.CAMPOS_DEL_PERFIL == (
        formulario.CAMPOS_PERFIL_PUBLICO + formulario.CAMPOS_CONTACTO
    )
    # Ningun campo repetido entre las dos pantallas: si uno cayera en las dos,
    # la union lo contaria dos veces y el dict lo pisaria sin avisar.
    assert len(set(formulario.CAMPOS_DEL_PERFIL)) == len(
        formulario.CAMPOS_DEL_PERFIL
    )


def test_campos_guardados_devuelve_exactamente_la_tupla_compartida(crear_usuario):
    """Las claves del dict que pinta el template, contra la fuente unica.

    Se compara la tupla entera y en orden, no `set(...)`: el orden de las
    claves es el orden en que se pintan los <input> de Ajustes.
    """
    usuario = crear_usuario(username="tomy")

    campos = formulario.campos_guardados(usuario)

    assert tuple(campos) == formulario.CAMPOS_DEL_PERFIL


def test_campos_guardados_sigue_a_la_tupla_y_no_a_una_lista_propia(
    crear_usuario, monkeypatch
):
    """El detector de la duplicacion, que es el punto del refactor.

    Agrega un campo ficticio a la tupla y exige que aparezca en el dict. Con la
    lista escrita a mano adentro de la funcion —como estaba— esto da rojo: la
    tupla decia nueve campos y el dict devolvia los ocho de siempre.

    Es la falla que se buscaba tapar, y era silenciosa: el campo nuevo no
    llegaba al template, se veia vacio al entrar a Ajustes y lo guardado en la
    base quedaba intacto, sin error en ningun lado.
    """
    usuario = crear_usuario(username="tomy")
    usuario.campo_ficticio = "un valor"
    monkeypatch.setattr(
        formulario,
        "CAMPOS_DEL_PERFIL",
        formulario.CAMPOS_DEL_PERFIL + ("campo_ficticio",),
    )

    campos = formulario.campos_guardados(usuario)

    assert campos["campo_ficticio"] == "un valor"


def test_lo_que_leen_las_dos_pantallas_cubre_todos_los_campos_guardados(app):
    """El otro lado del mismo olvido: agregar un campo y no leerlo del POST.

    Entre leer_perfil_publico() y leer_contacto() tienen que salir los ocho que
    campos_guardados() pinta, ni uno mas ni uno menos. Si alguien suma un campo
    a la tupla y no lo pone en ninguna de las dos pantallas, el <input> se
    dibuja pero lo que se escriba ahi no se guarda nunca.
    """
    with app.test_request_context():
        publico, _ = formulario.leer_perfil_publico()
        contacto, _ = formulario.leer_contacto()

    assert set(publico) | set(contacto) == set(formulario.CAMPOS_DEL_PERFIL)
