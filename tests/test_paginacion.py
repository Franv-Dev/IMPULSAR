"""El parcial de paginacion (`templates/partials/_paginacion.html`).

Lo usan once pantallas que paginan cosas distintas, asi que lo que se prueba
es lo que cada una le pasa y lo que el parcial hace con eso: que diga QUE
pagina, que avise cuando la pagina pedida no existe, y que la ficha vuelva a
su seccion de productos y no al tope.
"""

import re
from pathlib import Path

from models.product import Product

RAIZ = Path(__file__).resolve().parent.parent


def _html(respuesta):
    return respuesta.get_data(as_text=True)


def _nav_de_paginacion(html):
    nav = re.search(r'<nav class="pagination".*?</nav>', html, re.S)
    assert nav, "no se dibujo la paginacion"
    return nav.group(0)


def _ficha_con_productos(app, db, crear_usuario, crear_post, cuantos=5):
    """Un emprendimiento con mas productos que los que entran en una pagina."""
    app.config["PRODUCTOS_POR_PAGINA"] = 2
    autor = crear_usuario(username="autor")
    post = crear_post(autor.id)
    for i in range(cuantos):
        db.session.add(Product(post_id=post.id, nombre=f"Producto {i}", precio=100))
    db.session.commit()
    return post.id


def test_cada_pantalla_dice_que_esta_paginando():
    """Un aria-label fijo decia "emprendimientos" tambien sobre productos.

    Se recorren las plantillas y no una lista: una pantalla nueva que incluya
    el parcial sin etiqueta tiene que fallar aca el dia que se escribe.
    """
    sin_etiqueta = []
    for plantilla in list(RAIZ.glob("templates/**/*.html")) + list(RAIZ.glob("app/**/templates/**/*.html")):
        if plantilla.name == "_paginacion.html":
            continue                  # su comentario de uso cita el include
        texto = plantilla.read_text(encoding="utf-8")
        for include in re.finditer(r'\{% include "partials/_paginacion.html" %\}', texto):
            antes = texto[:include.start()]
            apertura = antes.rfind("{% with")
            if apertura == -1 or "{% endwith %}" in antes[apertura:] \
                    or "etiqueta_paginacion" not in antes[apertura:]:
                sin_etiqueta.append(str(plantilla.relative_to(RAIZ)))
    assert sin_etiqueta == []


def test_la_ficha_etiqueta_la_paginacion_como_productos(
    app, client, db, crear_usuario, crear_post
):
    post_id = _ficha_con_productos(app, db, crear_usuario, crear_post)
    nav = _nav_de_paginacion(_html(client.get(f"/blog/{post_id}")))
    assert 'aria-label="Paginación de productos"' in nav


def test_los_enlaces_de_la_ficha_vuelven_a_la_seccion_de_productos(
    app, client, db, crear_usuario, crear_post
):
    """Sin el ancla, cambiar de pagina en una ficha larga te subia al tope."""
    post_id = _ficha_con_productos(app, db, crear_usuario, crear_post)

    nav = _nav_de_paginacion(_html(client.get(f"/blog/{post_id}?page=2")))
    enlaces = re.findall(r'href="([^"]+)"', nav)
    assert len(enlaces) == 2          # anterior y siguiente
    for enlace in enlaces:
        assert enlace.endswith("#ficha-productos"), enlace


def test_el_catalogo_no_arrastra_el_ancla_de_la_ficha(
    app, client, db, crear_usuario, crear_post
):
    """El ancla es de la ficha: el catalogo es la lista entera y no la lleva."""
    _ficha_con_productos(app, db, crear_usuario, crear_post)
    nav = _nav_de_paginacion(_html(client.get("/productos/?page=2")))
    assert 'aria-label="Paginación de productos"' in nav
    assert "#" not in "".join(re.findall(r'href="([^"]+)"', nav))


def test_una_pagina_fuera_de_rango_avisa_en_vez_de_numerar(
    app, client, db, crear_usuario, crear_post
):
    """Con ?page=99 en un listado de 3 paginas se dibujaba "Página 99 de 3"."""
    post_id = _ficha_con_productos(app, db, crear_usuario, crear_post)

    nav = _nav_de_paginacion(_html(client.get(f"/blog/{post_id}?page=99")))
    assert "Página 99" not in nav
    assert "No hay más resultados: la última página es la 3." in nav
    # "Anterior" sigue llevando a la ultima pagina real.
    assert re.search(r'href="[^"]*page=3[^"]*"\s+rel="prev"', nav)

    # Y dentro del rango, el contador de siempre.
    nav = _nav_de_paginacion(_html(client.get(f"/blog/{post_id}?page=2")))
    assert "Página 2 de 3" in nav
    assert "No hay más resultados" not in nav
