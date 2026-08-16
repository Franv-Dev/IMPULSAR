"""Servicios de un emprendimiento: trabajos a presupuestar."""

from decimal import Decimal

import pytest

from models.service import MAX_SERVICIOS_POR_POST, Rubros, Service
from services.precios import parsear_precio


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


# --- precio opcional

def test_un_precio_vacio_no_es_error_si_no_es_obligatorio():
    """El caso del servicio a presupuestar."""
    precio, error = parsear_precio("", obligatorio=False)

    assert precio is None
    assert error is None


def test_un_precio_vacio_sigue_siendo_error_por_default():
    """El default no cambia: el producto sigue exigiendo precio."""
    precio, error = parsear_precio("")

    assert precio is None
    assert error


@pytest.mark.parametrize("texto", ["gratis", "-100", "1500,555", "1e5"])
def test_un_precio_escrito_mal_sigue_siendo_error_aunque_sea_opcional(texto):
    """Opcional es "podés no ponerlo", no "podés poner cualquier cosa"."""
    precio, error = parsear_precio(texto, obligatorio=False)

    assert precio is None
    assert error


def test_un_precio_opcional_bien_escrito_se_parsea_igual():
    precio, error = parsear_precio("1.500,50", obligatorio=False)

    assert error is None
    assert precio == Decimal("1500.50")


# --- ABM

@pytest.fixture
def emprendedor_con_post(crear_usuario, crear_post, login):
    """Un usuario logueado con un emprendimiento propio."""

    def _crear(username="tomy"):
        usuario = crear_usuario(username=username)
        post = crear_post(usuario.id)
        login(usuario.id)
        return usuario, post

    return _crear


def test_agregar_un_servicio_lo_guarda(client, emprendedor_con_post):
    _usuario, post = emprendedor_con_post()

    respuesta = client.post("/servicios/nuevo", data={
        "post_id": post.id,
        "titulo": "Destapación de cañerías",
        "rubro": Rubros.PLOMERIA,
        "descripcion": "Con máquina, sin romper",
        "zona_cobertura": "Maipú y alrededores",
        "precio_estimado": "15.000,50",
        "disponible": "on",
    })

    assert respuesta.status_code == 302
    servicio = Service.query.filter_by(post_id=post.id).one()
    assert servicio.titulo == "Destapación de cañerías"
    assert servicio.rubro == Rubros.PLOMERIA
    assert servicio.zona_cobertura == "Maipú y alrededores"
    assert servicio.precio_estimado == Decimal("15000.50")
    assert servicio.disponible is True


def test_un_servicio_sin_precio_se_guarda_a_presupuestar(client, emprendedor_con_post):
    """Es la diferencia con el producto: el precio vacio es valido."""
    _usuario, post = emprendedor_con_post()

    respuesta = client.post("/servicios/nuevo", data={
        "post_id": post.id, "titulo": "Instalación de termotanque",
        "rubro": Rubros.GAS, "precio_estimado": "", "disponible": "on",
    })

    assert respuesta.status_code == 302
    assert Service.query.one().precio_estimado is None


def test_un_servicio_sin_marcar_disponible_queda_oculto(client, emprendedor_con_post):
    """El checkbox sin marcar directamente no viaja en el POST."""
    _usuario, post = emprendedor_con_post()

    client.post("/servicios/nuevo", data={
        "post_id": post.id, "titulo": "Flete", "rubro": Rubros.FLETES,
    })

    assert Service.query.one().disponible is False


@pytest.mark.parametrize("campos", [
    {"titulo": "", "rubro": Rubros.PLOMERIA},
    {"titulo": "Destapaciones", "rubro": ""},
    # Un rubro que no esta en el catalogo: el <select> no lo ofrece, pero el
    # POST se puede mandar a mano.
    {"titulo": "Destapaciones", "rubro": "brujeria"},
    {"titulo": "Destapaciones", "rubro": Rubros.PLOMERIA, "precio_estimado": "gratis"},
])
def test_un_servicio_invalido_no_se_guarda(client, emprendedor_con_post, campos):
    _usuario, post = emprendedor_con_post()

    respuesta = client.post("/servicios/nuevo", data={"post_id": post.id, **campos})

    assert respuesta.status_code == 200  # vuelve al formulario
    assert Service.query.count() == 0


def test_no_se_puede_colgar_un_servicio_del_emprendimiento_de_otro(
    client, crear_usuario, crear_post, login
):
    ajeno = crear_usuario(username="ajeno")
    post_ajeno = crear_post(ajeno.id)
    intruso = crear_usuario(username="intruso")
    crear_post(intruso.id)
    login(intruso.id)

    client.post("/servicios/nuevo", data={
        "post_id": post_ajeno.id, "titulo": "Destapaciones", "rubro": Rubros.PLOMERIA,
    })

    assert Service.query.count() == 0


def test_no_se_puede_editar_un_servicio_ajeno(
    client, crear_usuario, crear_post, crear_servicio, login
):
    ajeno = crear_usuario(username="ajeno")
    post_ajeno = crear_post(ajeno.id)
    servicio = crear_servicio(post_ajeno.id, titulo="Destapaciones")
    intruso = crear_usuario(username="intruso")
    login(intruso.id)

    respuesta = client.post(f"/servicios/{servicio.id}/editar", data={
        "post_id": post_ajeno.id, "titulo": "Pisado", "rubro": Rubros.PLOMERIA,
    })

    assert respuesta.status_code == 302
    assert Service.query.get(servicio.id).titulo == "Destapaciones"


def test_no_se_puede_eliminar_un_servicio_ajeno(
    client, crear_usuario, crear_post, crear_servicio, login
):
    ajeno = crear_usuario(username="ajeno")
    post_ajeno = crear_post(ajeno.id)
    servicio = crear_servicio(post_ajeno.id)
    intruso = crear_usuario(username="intruso")
    login(intruso.id)

    respuesta = client.post(f"/servicios/{servicio.id}/eliminar")

    assert respuesta.status_code == 302
    assert Service.query.count() == 1


def test_eliminar_un_servicio_propio_lo_borra(client, emprendedor_con_post, crear_servicio):
    _usuario, post = emprendedor_con_post()
    servicio = crear_servicio(post.id)

    client.post(f"/servicios/{servicio.id}/eliminar")

    assert Service.query.count() == 0


def test_el_borrado_no_se_puede_disparar_con_un_get(
    client, emprendedor_con_post, crear_servicio
):
    """Un GET no debe tener efectos secundarios: lo dispara un prefetch."""
    _usuario, post = emprendedor_con_post()
    servicio = crear_servicio(post.id)

    respuesta = client.get(f"/servicios/{servicio.id}/eliminar")

    assert respuesta.status_code == 405
    assert Service.query.count() == 1


def test_el_panel_no_muestra_los_servicios_de_otro(
    client, crear_usuario, crear_post, crear_servicio, login
):
    ajeno = crear_usuario(username="ajeno")
    crear_servicio(crear_post(ajeno.id).id, titulo="Servicio ajeno")
    propio = crear_usuario(username="propio")
    crear_servicio(crear_post(propio.id, title="Lo mío").id, titulo="Servicio propio")
    login(propio.id)

    html = client.get("/servicios/").get_data(as_text=True)

    assert "Servicio propio" in html
    assert "Servicio ajeno" not in html


def test_el_tope_corta_el_alta(client, emprendedor_con_post, crear_servicio, monkeypatch):
    """Con el tope real habria que crear 50 filas; se baja a 2 para el test,
    que es lo que se esta probando (que el tope corte), no el numero."""
    import views.servicios as vista

    _usuario, post = emprendedor_con_post()
    monkeypatch.setattr(vista, "MAX_SERVICIOS_POR_POST", 2)
    crear_servicio(post.id, titulo="Uno")
    crear_servicio(post.id, titulo="Dos")

    client.post("/servicios/nuevo", data={
        "post_id": post.id, "titulo": "Tres", "rubro": Rubros.PLOMERIA,
    })

    assert Service.query.count() == 2


def test_servicios_esta_en_los_slugs_reservados():
    """/servicios es una ruta de primer nivel: un usuario con ese slug no la
    tapa hoy (el perfil vive bajo /perfil/), pero se reserva igual, con el
    mismo criterio que "blog", "mensajes", "favoritos" y "eventos"."""
    from services.slugs import SLUGS_RESERVADOS

    assert "servicios" in SLUGS_RESERVADOS
