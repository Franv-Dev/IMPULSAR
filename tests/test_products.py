"""Catalogo de productos de un emprendimiento."""

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
