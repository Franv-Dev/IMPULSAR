"""Catalogo de productos de un emprendimiento."""

import os
from decimal import Decimal

import pytest

from models.product import MAX_PRODUCTOS_POR_POST, Product
from services.precios import formatear, parsear_precio, texto_para_formulario


@pytest.fixture
def crear_producto(db):
    """Fabrica de productos."""

    def _crear(post_id, nombre="Pan de campo", precio="1500.00",
               descripcion=None, foto=None, disponible=True):
        producto = Product(
            post_id=post_id,
            nombre=nombre,
            descripcion=descripcion,
            precio=Decimal(precio),
            foto=foto,
            disponible=disponible,
        )
        db.session.add(producto)
        db.session.commit()
        return producto

    return _crear


# --- precios

@pytest.mark.parametrize("texto, esperado", [
    ("1500", "1500.00"),
    ("1500,50", "1500.50"),
    ("1500.50", "1500.50"),
    # Con puntos de miles y coma decimal, como se escribe en Argentina.
    ("1.500,50", "1500.50"),
    ("$ 1500", "1500.00"),
    ("0,01", "0.01"),
])
def test_parsear_precio_acepta_como_escribe_la_gente(texto, esperado):
    precio, error = parsear_precio(texto)

    assert error is None
    assert precio == Decimal(esperado)


@pytest.mark.parametrize("texto", [
    "", None, "gratis", "-100", "0", "1500,555", "999999999", "1e5",
])
def test_parsear_precio_rechaza_lo_que_no_es_un_precio(texto):
    precio, error = parsear_precio(texto)

    assert precio is None
    assert error


def test_el_precio_queda_normalizado_a_dos_decimales():
    """Asi "1500" y "1500,00" se guardan igual y el formulario de edicion
    siempre muestra lo mismo."""
    assert parsear_precio("1500")[0].as_tuple().exponent == -2


def test_formatear_usa_los_separadores_de_argentina():
    assert formatear(Decimal("1500.50")) == "$ 1.500,50"
    assert formatear(Decimal("999.00")) == "$ 999,00"
    assert formatear(None) == ""


def test_el_texto_del_formulario_lo_vuelve_a_leer_parsear_precio():
    """Editar un producto sin tocar el precio no tiene que cambiarlo."""
    original = Decimal("1234.56")

    releido, error = parsear_precio(texto_para_formulario(original))

    assert error is None
    assert releido == original


# --- modelo

def test_el_precio_vuelve_de_la_base_como_decimal_exacto(
    db, crear_usuario, crear_post, crear_producto
):
    """La razon de usar Numeric y no Float: con Float, 1999.95 vuelve como
    1999.9499999... y cualquier suma de precios arrastra el error."""
    autor = crear_usuario(username="autor")
    post = crear_post(autor.id)
    producto = crear_producto(post.id, precio="1999.95")
    db.session.expire_all()

    guardado = db.session.get(Product, producto.id)

    assert isinstance(guardado.precio, Decimal)
    assert guardado.precio == Decimal("1999.95")


def test_un_producto_nace_disponible(db, crear_usuario, crear_post):
    autor = crear_usuario(username="autor")
    post = crear_post(autor.id)
    producto = Product(post_id=post.id, nombre="Pan", precio=Decimal("100.00"))
    db.session.add(producto)
    db.session.commit()

    assert producto.disponible is True


def test_los_productos_del_post_salen_en_orden_alfabetico(
    db, crear_usuario, crear_post, crear_producto
):
    autor = crear_usuario(username="autor")
    post = crear_post(autor.id)
    crear_producto(post.id, nombre="Torta")
    crear_producto(post.id, nombre="Alfajores")
    crear_producto(post.id, nombre="Pan")
    db.session.expire_all()

    assert [p.nombre for p in post.productos] == ["Alfajores", "Pan", "Torta"]


def test_borrar_un_emprendimiento_se_lleva_sus_productos(
    db, crear_usuario, crear_post, crear_producto
):
    """El bug de FK RESTRICT que ya aparecio en reports, favorites, messages y
    post_images: aca la FK nace con ON DELETE CASCADE."""
    autor = crear_usuario(username="autor")
    post = crear_post(autor.id)
    crear_producto(post.id)
    post_id = post.id

    db.session.delete(post)
    db.session.commit()

    assert Product.query.filter_by(post_id=post_id).count() == 0


def test_borrar_un_usuario_se_lleva_los_productos_de_sus_emprendimientos(
    db, crear_usuario, crear_post, crear_producto
):
    autor = crear_usuario(username="autor")
    post = crear_post(autor.id)
    crear_producto(post.id)
    post_id = post.id

    db.session.delete(autor)
    db.session.commit()

    assert Product.query.filter_by(post_id=post_id).count() == 0


def test_el_tope_por_emprendimiento_es_un_numero_razonable():
    """No es configurable todavia (ver models/product.py), pero que quede
    fijado en un test: bajarlo de golpe romperia catalogos ya cargados."""
    assert MAX_PRODUCTOS_POR_POST == 50


# --- ABM: helpers

@pytest.fixture
def emprendedor_con_post(crear_usuario, crear_post, login):
    """Un usuario logueado con un emprendimiento propio."""

    def _crear(username="tomy"):
        usuario = crear_usuario(username=username)
        post = crear_post(usuario.id)
        login(usuario.id)
        return usuario, post

    return _crear


def _imagen(nombre="producto.png", color="blue"):
    """Un archivo de imagen valido, listo para subir en un multipart."""
    import io

    from PIL import Image
    from werkzeug.datastructures import FileStorage

    buffer = io.BytesIO()
    Image.new("RGB", (10, 10), color).save(buffer, format="PNG")
    buffer.seek(0)
    return FileStorage(stream=buffer, filename=nombre, content_type="image/png")


def _ruta_de_upload(app, nombre):
    return os.path.join(app.root_path, "static", "uploads", nombre)


# --- ABM: alta

def test_agregar_un_producto_lo_guarda(client, emprendedor_con_post):
    _usuario, post = emprendedor_con_post()

    respuesta = client.post("/productos/nuevo", data={
        "post_id": post.id,
        "nombre": "Pan de campo",
        "descripcion": "De masa madre",
        "precio": "1.500,50",
        "disponible": "on",
    })

    assert respuesta.status_code == 302
    producto = Product.query.filter_by(post_id=post.id).one()
    assert producto.nombre == "Pan de campo"
    assert producto.precio == Decimal("1500.50")
    assert producto.disponible is True


def test_un_producto_sin_marcar_disponible_queda_sin_stock(client, emprendedor_con_post):
    """El checkbox sin marcar directamente no viaja en el POST."""
    _usuario, post = emprendedor_con_post()

    client.post("/productos/nuevo", data={
        "post_id": post.id, "nombre": "Torta", "precio": "5000",
    })

    assert Product.query.one().disponible is False


@pytest.mark.parametrize("campos", [
    {"nombre": "", "precio": "1500"},
    {"nombre": "Pan", "precio": ""},
    {"nombre": "Pan", "precio": "gratis"},
    {"nombre": "Pan", "precio": "-5"},
])
def test_un_producto_invalido_no_se_guarda(client, emprendedor_con_post, campos):
    _usuario, post = emprendedor_con_post()

    respuesta = client.post("/productos/nuevo", data={"post_id": post.id, **campos})

    assert respuesta.status_code == 200  # vuelve al formulario
    assert Product.query.count() == 0


def test_no_se_puede_colgar_un_producto_del_emprendimiento_de_otro(
    client, crear_usuario, crear_post, login
):
    ajeno = crear_usuario(username="ajeno")
    post_ajeno = crear_post(ajeno.id)
    intruso = crear_usuario(username="intruso")
    crear_post(intruso.id)
    login(intruso.id)

    client.post("/productos/nuevo", data={
        "post_id": post_ajeno.id, "nombre": "Pan", "precio": "1500",
    })

    assert Product.query.filter_by(post_id=post_ajeno.id).count() == 0


def test_sin_emprendimientos_no_se_puede_cargar_un_producto(client, crear_usuario, login):
    usuario = crear_usuario(username="sin_posts")
    login(usuario.id)

    respuesta = client.post("/productos/nuevo", data={
        "post_id": 1, "nombre": "Pan", "precio": "1500",
    })

    assert respuesta.status_code == 302
    assert Product.query.count() == 0


def test_el_abm_requiere_estar_logueado(client):
    for url in ("/productos/", "/productos/nuevo"):
        assert client.get(url).status_code == 302


def test_no_se_pueden_pasar_del_maximo(client, emprendedor_con_post, crear_producto):
    _usuario, post = emprendedor_con_post()
    for numero in range(MAX_PRODUCTOS_POR_POST):
        crear_producto(post.id, nombre=f"Producto {numero:03d}")

    respuesta = client.post("/productos/nuevo", data={
        "post_id": post.id, "nombre": "Uno de mas", "precio": "1500",
    })

    assert respuesta.status_code == 200
    assert Product.query.count() == MAX_PRODUCTOS_POR_POST


# --- ABM: edicion y borrado

def test_el_dueno_edita_su_producto(client, db, emprendedor_con_post, crear_producto):
    _usuario, post = emprendedor_con_post()
    producto = crear_producto(post.id, nombre="Pan", precio="1500.00")

    client.post(f"/productos/{producto.id}/editar", data={
        "post_id": post.id, "nombre": "Pan integral",
        "precio": "1800", "disponible": "on",
    })

    db.session.refresh(producto)
    assert producto.nombre == "Pan integral"
    assert producto.precio == Decimal("1800.00")


def test_editar_sin_tocar_el_precio_no_lo_cambia(
    client, db, emprendedor_con_post, crear_producto
):
    """El formulario precarga el precio con texto_para_formulario: reenviarlo
    tal cual tiene que dejar el mismo Decimal."""
    _usuario, post = emprendedor_con_post()
    producto = crear_producto(post.id, precio="1234.56")

    pagina = client.get(f"/productos/{producto.id}/editar").get_data(as_text=True)
    assert 'value="1234.56"' in pagina

    client.post(f"/productos/{producto.id}/editar", data={
        "post_id": post.id, "nombre": producto.nombre,
        "precio": "1234.56", "disponible": "on",
    })

    db.session.refresh(producto)
    assert producto.precio == Decimal("1234.56")


def test_el_dueno_elimina_su_producto(client, emprendedor_con_post, crear_producto):
    _usuario, post = emprendedor_con_post()
    producto = crear_producto(post.id)

    respuesta = client.post(f"/productos/{producto.id}/eliminar")

    assert respuesta.status_code == 302
    assert Product.query.count() == 0


def test_un_extrano_no_puede_editar_un_producto_ajeno(
    client, db, crear_usuario, crear_post, crear_producto, login
):
    dueno = crear_usuario(username="dueno")
    post = crear_post(dueno.id)
    producto = crear_producto(post.id, nombre="Pan")
    intruso = crear_usuario(username="intruso")
    crear_post(intruso.id)
    login(intruso.id)

    respuesta = client.post(f"/productos/{producto.id}/editar", data={
        "post_id": post.id, "nombre": "Robado", "precio": "1",
    })

    assert respuesta.status_code == 302
    db.session.refresh(producto)
    assert producto.nombre == "Pan"


def test_un_extrano_no_puede_eliminar_un_producto_ajeno(
    client, crear_usuario, crear_post, crear_producto, login
):
    dueno = crear_usuario(username="dueno")
    post = crear_post(dueno.id)
    producto = crear_producto(post.id)
    intruso = crear_usuario(username="intruso")
    login(intruso.id)

    respuesta = client.post(f"/productos/{producto.id}/eliminar")

    assert respuesta.status_code == 302
    assert Product.query.count() == 1


def test_eliminar_no_acepta_get(client, emprendedor_con_post, crear_producto):
    """Un GET no debe tener efectos: lo puede disparar un prefetch o un crawler."""
    _usuario, post = emprendedor_con_post()
    producto = crear_producto(post.id)

    respuesta = client.get(f"/productos/{producto.id}/eliminar")

    assert respuesta.status_code == 405
    assert Product.query.count() == 1


# --- ABM: fotos en disco

def test_eliminar_un_producto_borra_su_foto_del_disco(client, app, emprendedor_con_post):
    """El bug de fotos huerfanas que ya se arreglo en la galeria: la fila se va
    y el archivo queda ocupando disco para siempre."""
    _usuario, post = emprendedor_con_post()
    client.post("/productos/nuevo", data={
        "post_id": post.id, "nombre": "Pan", "precio": "1500", "foto": _imagen(),
    }, content_type="multipart/form-data")
    producto = Product.query.one()
    ruta = _ruta_de_upload(app, producto.foto)
    assert os.path.exists(ruta)

    client.post(f"/productos/{producto.id}/eliminar")

    assert not os.path.exists(ruta)


def test_cambiar_la_foto_borra_la_anterior(client, app, emprendedor_con_post):
    _usuario, post = emprendedor_con_post()
    client.post("/productos/nuevo", data={
        "post_id": post.id, "nombre": "Pan", "precio": "1500",
        "foto": _imagen("vieja.png"),
    }, content_type="multipart/form-data")
    producto = Product.query.one()
    vieja = _ruta_de_upload(app, producto.foto)

    client.post(f"/productos/{producto.id}/editar", data={
        "post_id": post.id, "nombre": "Pan", "precio": "1500",
        "disponible": "on", "foto": _imagen("nueva.png"),
    }, content_type="multipart/form-data")

    assert not os.path.exists(vieja)
    assert os.path.exists(_ruta_de_upload(app, Product.query.one().foto))


def test_una_foto_invalida_no_guarda_el_producto(client, emprendedor_con_post):
    import io

    from werkzeug.datastructures import FileStorage

    _usuario, post = emprendedor_con_post()
    rota = FileStorage(
        stream=io.BytesIO(b"esto no es una imagen"),
        filename="rota.png",
        content_type="image/png",
    )

    respuesta = client.post("/productos/nuevo", data={
        "post_id": post.id, "nombre": "Pan", "precio": "1500", "foto": rota,
    }, content_type="multipart/form-data")

    assert respuesta.status_code == 200
    assert Product.query.count() == 0


# --- panel

def test_el_panel_muestra_solo_los_productos_propios(
    client, crear_usuario, crear_post, crear_producto, login
):
    dueno = crear_usuario(username="dueno")
    crear_producto(crear_post(dueno.id).id, nombre="Pan propio")
    ajeno = crear_usuario(username="ajeno")
    crear_producto(crear_post(ajeno.id).id, nombre="Pan ajeno")
    login(dueno.id)

    html = client.get("/productos/").get_data(as_text=True)

    assert "Pan propio" in html
    assert "Pan ajeno" not in html


def test_el_panel_muestra_el_precio_formateado(
    client, emprendedor_con_post, crear_producto
):
    _usuario, post = emprendedor_con_post()
    crear_producto(post.id, precio="1500.50")

    html = client.get("/productos/").get_data(as_text=True)

    assert "$ 1.500,50" in html


# --- catalogo publico

def test_el_catalogo_se_ve_en_la_pagina_del_emprendimiento(
    client, crear_usuario, crear_post, crear_producto
):
    autor = crear_usuario(username="autor")
    post = crear_post(autor.id)
    crear_producto(post.id, nombre="Pan de campo", precio="1500.50")

    html = client.get(f"/blog/{post.id}").get_data(as_text=True)

    assert "Pan de campo" in html
    assert "$ 1.500,50" in html


def test_un_visitante_no_ve_los_productos_sin_stock(
    client, crear_usuario, crear_post, crear_producto
):
    autor = crear_usuario(username="autor")
    post = crear_post(autor.id)
    crear_producto(post.id, nombre="Pan disponible")
    crear_producto(post.id, nombre="Torta agotada", disponible=False)

    html = client.get(f"/blog/{post.id}").get_data(as_text=True)

    assert "Pan disponible" in html
    # No alcanza con no mostrarlo: si viajara al HTML se leeria en el codigo
    # fuente igual, por eso el filtro va en la consulta.
    assert "Torta agotada" not in html


def test_otro_usuario_logueado_tampoco_ve_los_sin_stock(
    client, crear_usuario, crear_post, crear_producto, login
):
    autor = crear_usuario(username="autor")
    post = crear_post(autor.id)
    crear_producto(post.id, nombre="Torta agotada", disponible=False)
    curioso = crear_usuario(username="curioso")
    login(curioso.id)

    html = client.get(f"/blog/{post.id}").get_data(as_text=True)

    assert "Torta agotada" not in html


def test_el_dueno_ve_tambien_los_sin_stock(
    client, crear_usuario, crear_post, crear_producto, login
):
    autor = crear_usuario(username="autor")
    post = crear_post(autor.id)
    crear_producto(post.id, nombre="Torta agotada", disponible=False)
    login(autor.id)

    html = client.get(f"/blog/{post.id}").get_data(as_text=True)

    assert "Torta agotada" in html


def test_el_catalogo_de_un_emprendimiento_no_muestra_el_de_otro(
    client, crear_usuario, crear_post, crear_producto
):
    autor = crear_usuario(username="autor")
    panaderia = crear_post(autor.id, title="Panaderia")
    huerta = crear_post(autor.id, title="Huerta")
    crear_producto(panaderia.id, nombre="Pan de campo")
    crear_producto(huerta.id, nombre="Lechuga")

    html = client.get(f"/blog/{panaderia.id}").get_data(as_text=True)

    assert "Pan de campo" in html
    assert "Lechuga" not in html


def test_sin_productos_el_visitante_no_ve_la_seccion(
    client, crear_usuario, crear_post
):
    autor = crear_usuario(username="autor")
    post = crear_post(autor.id)

    html = client.get(f"/blog/{post.id}").get_data(as_text=True)

    assert "Qué vende" not in html


def test_sin_productos_el_dueno_ve_la_invitacion_a_cargar(
    client, crear_usuario, crear_post, login
):
    autor = crear_usuario(username="autor")
    post = crear_post(autor.id)
    login(autor.id)

    html = client.get(f"/blog/{post.id}").get_data(as_text=True)

    assert "Qué vende" in html
    assert "/productos/nuevo" in html


def test_el_visitante_no_ve_el_boton_de_editar_el_catalogo(
    client, crear_usuario, crear_post, crear_producto
):
    autor = crear_usuario(username="autor")
    post = crear_post(autor.id)
    crear_producto(post.id)

    html = client.get(f"/blog/{post.id}").get_data(as_text=True)

    assert "Editar catálogo" not in html


def test_el_catalogo_sale_ordenado_alfabeticamente(
    client, crear_usuario, crear_post, crear_producto
):
    autor = crear_usuario(username="autor")
    post = crear_post(autor.id)
    crear_producto(post.id, nombre="Torta")
    crear_producto(post.id, nombre="Alfajores")

    html = client.get(f"/blog/{post.id}").get_data(as_text=True)

    assert html.index("Alfajores") < html.index("Torta")


def test_el_catalogo_no_dispara_una_consulta_por_producto(
    client, db, crear_usuario, crear_post, crear_producto
):
    """El catalogo se trae con una sola consulta, no una por producto: sin eso,
    un emprendimiento con 50 productos hace 50 SELECT para mostrar la pagina."""
    from sqlalchemy import event

    autor = crear_usuario(username="autor")
    post = crear_post(autor.id)
    for numero in range(5):
        crear_producto(post.id, nombre=f"Producto {numero}")

    consultas = []

    def contar(conn, cursor, statement, *args):
        if "products" in statement.lower():
            consultas.append(statement)

    event.listen(db.engine, "before_cursor_execute", contar)
    try:
        client.get(f"/blog/{post.id}")
    finally:
        event.remove(db.engine, "before_cursor_execute", contar)

    assert len(consultas) == 1
