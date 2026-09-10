"""Las seis paginas de contenido: Sobre, Contacto, las dos legales y los errores.

Son rutas sin logica (views/pages.py es un render_template por pagina), asi que
lo que se prueba es lo que la tanda de disenio-paginas/ decidio que tienen que
decir y que no: el texto viejo que hablaba del equipo de desarrollo, el emoji
del mail, las listas que no eran listas, y la diferencia entre el 404 y el 500.

Son tests de CONTENIDO y no de estilo: ninguno mira una clase de CSS salvo
cuando la clase es la unica forma de preguntar si un bloque esta o no.
"""

from app.blog.modelo_post import Categorias


def _html(respuesta):
    return respuesta.get_data(as_text=True)


# --- las cuatro rutas siguen donde estaban

def test_las_cuatro_paginas_responden(client):
    """Las URL no cambian: las tiene el pie de todas las pantallas."""
    for url in ("/sobre/", "/contacto/", "/terminos/", "/privacidad/"):
        assert client.get(url).status_code == 200, url


# --- Sobre

def test_sobre_ya_no_habla_del_equipo_de_desarrollo(client):
    """El texto viejo contaba con qué está hecha la app, no qué resuelve.

    Decía «desarrollada por un equipo académico utilizando Flask (Python) y
    MySQL, siguiendo buenas prácticas de diseño y una estética moderna en tonos
    pastel». Lo de pastel además hace rato que es falso: la paleta es el índigo
    del logo.
    """
    html = _html(client.get("/sobre/"))

    assert "Flask" not in html
    assert "MySQL" not in html
    assert "pastel" not in html
    assert "equipo académico" not in html


def test_sobre_dice_lo_que_impulsar_no_hace(client):
    """Es parte del argumento, no una disculpa: sin pagos, sin envíos, sin
    protección al comprador. Decirlo acá es lo que evita que alguien se sienta
    estafado a mitad del chat."""
    html = _html(client.get("/sobre/"))

    assert "Lo que IMPULSAR no hace" in html
    assert "No procesamos pagos" in html
    assert "No hacemos envíos" in html
    assert "No hay protección al comprador" in html


def test_sobre_no_tiene_numeros_inventados(client):
    """Cuántos emprendimientos, desde cuándo o cuánta gente son datos que no
    existen. La página no los tiene, y este test es lo que impide que alguien
    los agregue de memoria."""
    html = _html(client.get("/sobre/"))
    cuerpo = html.split('<main>')[1].split('</main>')[0]

    for invento in ("+1.000", "más de 100", "desde 2023", "miles de"):
        assert invento not in cuerpo


def test_sobre_lleva_a_publicar_y_a_contacto(client):
    html = _html(client.get("/sobre/"))

    assert "Publicar mi emprendimiento" in html
    assert "/contacto/" in html


# --- Contacto

def test_contacto_no_tiene_el_emoji_del_sobre(client):
    """La guía sólo admite emoji si son de la marca; ahí era decoración."""
    html = _html(client.get("/contacto/"))

    assert "📧" not in html
    assert "impulsARmdz@gmail.com" in html


def test_contacto_sigue_sin_formulario(client):
    """No hay tabla de consultas ni envío de mail: la ruta es un
    render_template sin lógica. Un formulario dibujado que en realidad no manda
    nada es peor que un mailto honesto."""
    html = _html(client.get("/contacto/"))
    cuerpo = html.split('<main>')[1].split('</main>')[0]

    assert "<form" not in cuerpo
    assert "mailto:impulsARmdz@gmail.com" in cuerpo


def test_contacto_ofrece_los_cuatro_atajos(client):
    """Sin ellos la casilla se vuelve el cajón donde caen «este emprendimiento
    es trucho» y «quiero cambiar mi mail», que la app ya resuelve sola."""
    html = _html(client.get("/contacto/"))

    assert "Reportar un emprendimiento o una reseña" in html
    assert "Preguntarle algo a un emprendimiento" in html
    assert "Publicar tu emprendimiento" in html
    assert "Cambiar tus datos o cerrar tu cuenta" in html


def test_los_atajos_de_cuenta_llevan_a_entrar_sin_sesion(client):
    """Sin sesión no hay Ajustes a donde ir: el atajo tiene que rebotar a
    entrar y no a una URL que va a dar 302 igual."""
    html = _html(client.get("/contacto/"))

    assert "/auth/login" in html


def test_los_atajos_de_cuenta_llevan_a_ajustes_con_sesion(client, crear_usuario, login):
    usuario = crear_usuario()
    login(usuario.id)

    html = _html(client.get("/contacto/"))

    assert "/perfil/edit" in html
    assert "/blog/create" in html


# --- las dos legales

def test_las_legales_no_cambiaron_una_palabra(client):
    """Lo que cambió es la forma, no el texto: eso no se toca sin que lo diga
    Tomás."""
    privacidad = _html(client.get("/privacidad/"))
    terminos = _html(client.get("/terminos/"))

    assert "nos tomamos en serio la protección de tus datos" in privacidad
    assert "No vendemos ni compartimos tus datos personales con terceros" in privacidad
    assert "implica la aceptación de" in terminos
    assert "no se responsabiliza por" in terminos


def test_la_lista_de_privacidad_es_una_lista_de_verdad(client):
    """Estaba hecha con «<br>•» adentro de un <p>: se ve igual, pero para un
    lector de pantalla es un párrafo con puntos medios, no una lista."""
    html = _html(client.get("/privacidad/"))
    cuerpo = html.split('<main>')[1].split('</main>')[0]

    assert "<ul" in cuerpo
    assert "<br>•" not in cuerpo
    assert "•" not in cuerpo
    assert "Crear y gestionar tu cuenta de usuario." in cuerpo


def test_el_indice_lleva_a_secciones_que_existen(client):
    """Un índice que apunta a un ancla inexistente es un link muerto."""
    for url in ("/privacidad/", "/terminos/"):
        html = _html(client.get(url))
        cuerpo = html.split('<main>')[1].split('</main>')[0]

        anclas = set()
        for trozo in cuerpo.split('href="#')[1:]:
            anclas.add(trozo.split('"')[0])
        assert anclas, f"{url} no tiene índice"

        for ancla in anclas:
            assert f'id="{ancla}"' in cuerpo, f"{url}: el índice apunta a #{ancla} y no existe"


def test_cada_legal_enlaza_a_la_otra(client):
    """Quien viene a leer una casi siempre termina buscando la otra."""
    assert "/terminos/" in _html(client.get("/privacidad/"))
    assert "/privacidad/" in _html(client.get("/terminos/"))


def test_sin_fecha_cargada_no_se_dibuja_la_pastilla(client):
    """Ninguna de las dos legales tiene fecha de última actualización todavía,
    y no es un dato que se pueda inventar: hasta que esté, la pastilla no
    aparece (ver ACTUALIZADA_* en views/pages.py). Un «[COMPLETAR]» a la vista
    del usuario sería peor que no decir nada."""
    for url in ("/privacidad/", "/terminos/"):
        html = _html(client.get(url))
        assert "Última actualización" not in html, url
        assert "COMPLETAR" not in html, url


def test_con_fecha_cargada_se_dibuja_la_pastilla(client, monkeypatch):
    """La otra mitad: cuando la constante esté puesta, la pastilla sale sola y
    sin tocar el template."""
    import views.pages as pages

    monkeypatch.setattr(pages, "ACTUALIZADA_PRIVACIDAD", "14 de agosto de 2026")

    html = _html(client.get("/privacidad/"))

    assert "Última actualización: 14 de agosto de 2026" in html


# --- 404 y 500

def test_el_404_lleva_buscador_y_los_siete_rubros(client):
    """Un 404 no es un cartel, es una bifurcación: casi siempre se llega desde
    un emprendimiento dado de baja o un link viejo, y la persona venía a buscar
    algo concreto."""
    html = _html(client.get("/una-url-que-no-existe"))
    cuerpo = html.split('<main>')[1].split('</main>')[0]

    assert 'id="error-q"' in cuerpo
    for etiqueta in Categorias.ETIQUETAS.values():
        assert etiqueta in cuerpo, etiqueta


def test_los_rubros_del_404_llevan_al_listado_filtrado(client):
    html = _html(client.get("/una-url-que-no-existe"))

    for valor in Categorias.TODAS:
        assert f"category={valor}" in html, valor


def test_el_buscador_del_404_manda_al_listado(client):
    """Acá no se resuelve la búsqueda, se reencamina a donde vive."""
    html = _html(client.get("/una-url-que-no-existe"))

    assert 'action="/blog/"' in html
    assert 'name="q"' in html


def test_el_500_no_lleva_buscador_ni_rubros(app):
    """Si el servidor se cayó, ofrecer un buscador que tampoco va a andar es
    una segunda frustración."""
    from flask import render_template

    with app.test_request_context("/algo/que/fallo"):
        html = render_template("errors/500.html")

    assert "error__buscador" not in html
    assert "error__rubro" not in html
    assert "Algo salió mal de nuestro lado" in html


def test_el_500_ofrece_reintentar_y_contacto(app):
    """Y no «ver emprendimientos», que es justo lo que puede estar roto."""
    from flask import render_template

    with app.test_request_context("/algo/que/fallo"):
        html = render_template("errors/500.html")

    assert "Reintentar" in html
    assert "/algo/que/fallo" in html
    assert "/contacto/" in html
