"""Servicios de un emprendimiento: trabajos a presupuestar."""

from decimal import Decimal

import pytest

from models.service import MAX_SERVICIOS_POR_POST, Rubros, Service


@pytest.fixture
def crear_servicio(db):
    """Fabrica de servicios."""

    def _crear(post_id, titulo="Destapaciones", rubro=Rubros.PLOMERIA,
               descripcion=None, zona_cobertura=None, precio_estimado=None,
               disponible=True):
        servicio = Service(
            post_id=post_id,
            titulo=titulo,
            rubro=rubro,
            descripcion=descripcion,
            zona_cobertura=zona_cobertura,
            precio_estimado=(
                Decimal(precio_estimado) if precio_estimado is not None else None
            ),
            disponible=disponible,
        )
        db.session.add(servicio)
        db.session.commit()
        return servicio

    return _crear


# --- modelo

def test_un_servicio_puede_no_tener_precio(db, crear_usuario, crear_post, crear_servicio):
    """La diferencia con Product, que tiene precio NOT NULL: un servicio se
    cotiza contra el caso de cada cliente."""
    autor = crear_usuario(username="autor")
    post = crear_post(autor.id)
    servicio = crear_servicio(post.id)
    db.session.expire_all()

    guardado = db.session.get(Service, servicio.id)

    assert guardado.precio_estimado is None


def test_el_precio_estimado_vuelve_de_la_base_como_decimal_exacto(
    db, crear_usuario, crear_post, crear_servicio
):
    """La razon de usar Numeric y no Float, igual que en productos."""
    autor = crear_usuario(username="autor")
    post = crear_post(autor.id)
    servicio = crear_servicio(post.id, precio_estimado="1999.95")
    db.session.expire_all()

    guardado = db.session.get(Service, servicio.id)

    assert isinstance(guardado.precio_estimado, Decimal)
    assert guardado.precio_estimado == Decimal("1999.95")


def test_un_servicio_nace_disponible(db, crear_usuario, crear_post):
    autor = crear_usuario(username="autor")
    post = crear_post(autor.id)
    servicio = Service(post_id=post.id, titulo="Destapaciones", rubro=Rubros.PLOMERIA)
    db.session.add(servicio)
    db.session.commit()

    assert servicio.disponible is True


def test_un_servicio_sin_rubro_queda_en_otros(db, crear_usuario, crear_post):
    """El default de la columna, para que ninguna fila quede sin rubro: la
    busqueda por rubro de la proxima tanda las perderia."""
    autor = crear_usuario(username="autor")
    post = crear_post(autor.id)
    servicio = Service(post_id=post.id, titulo="Algo")
    db.session.add(servicio)
    db.session.commit()

    assert servicio.rubro == Rubros.OTROS


def test_cada_rubro_tiene_su_etiqueta():
    """Sin esto, un rubro nuevo se muestra crudo ("albanileria") en la
    interfaz. Mismo chequeo que se le hace a Categorias."""
    assert set(Rubros.TODOS) == set(Rubros.ETIQUETAS)


def test_los_servicios_del_post_salen_en_orden_alfabetico(
    db, crear_usuario, crear_post, crear_servicio
):
    autor = crear_usuario(username="autor")
    post = crear_post(autor.id)
    crear_servicio(post.id, titulo="Destapaciones")
    crear_servicio(post.id, titulo="Arreglo de canillas")
    crear_servicio(post.id, titulo="Instalación de termotanque")
    db.session.expire_all()

    assert [s.titulo for s in post.servicios] == [
        "Arreglo de canillas", "Destapaciones", "Instalación de termotanque",
    ]


def test_borrar_un_emprendimiento_se_lleva_sus_servicios(
    db, crear_usuario, crear_post, crear_servicio
):
    """El bug de FK RESTRICT que aparecio en reports, favorites, messages y
    post_images: aca la FK nace con ON DELETE CASCADE."""
    autor = crear_usuario(username="autor")
    post = crear_post(autor.id)
    crear_servicio(post.id)
    post_id = post.id

    db.session.delete(post)
    db.session.commit()

    assert Service.query.filter_by(post_id=post_id).count() == 0


def test_borrar_un_usuario_se_lleva_los_servicios_de_sus_emprendimientos(
    db, crear_usuario, crear_post, crear_servicio
):
    autor = crear_usuario(username="autor")
    post = crear_post(autor.id)
    crear_servicio(post.id)
    post_id = post.id

    db.session.delete(autor)
    db.session.commit()

    assert Service.query.filter_by(post_id=post_id).count() == 0


def test_el_tope_por_emprendimiento_es_el_mismo_que_el_de_productos():
    """Mismo numero y mismo criterio (ver models/service.py). Queda fijado en
    un test porque bajarlo de golpe romperia lo que ya este cargado."""
    from models.product import MAX_PRODUCTOS_POR_POST

    assert MAX_SERVICIOS_POR_POST == MAX_PRODUCTOS_POR_POST == 50


def test_serialize_no_manda_el_precio_como_float(
    db, crear_usuario, crear_post, crear_servicio
):
    autor = crear_usuario(username="autor")
    post = crear_post(autor.id)
    con_precio = crear_servicio(post.id, precio_estimado="1999.95")
    sin_precio = crear_servicio(post.id, titulo="A presupuestar")

    assert con_precio.serialize()["precio_estimado"] == "1999.95"
    # None y no 0: "a presupuestar" no es "sale cero".
    assert sin_precio.serialize()["precio_estimado"] is None
