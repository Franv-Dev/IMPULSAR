"""Servicios de un emprendimiento: trabajos a presupuestar."""

import os
import threading
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError

from app.servicios.modelo import MAX_SERVICIOS_POR_POST, Rubros, Service
from app.servicios.modelo_solicitud import EstadosSolicitud, ServiceRequest
from app.servicios.modelo_verificacion import (
    EstadosVerificacion, VerificationRequest,
)
from config import Config
from db import db as _db
from main import create_app
from app.blog.modelo_post import Post
from models.user import Roles, User
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
    """Mismo numero y mismo criterio (ver app/servicios/modelo.py). Queda fijado en
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
    from app.servicios import reglas

    _usuario, post = emprendedor_con_post()
    # El tope lo decide reglas.hay_lugar, asi que el que manda es el nombre que
    # ve ese modulo.
    monkeypatch.setattr(reglas, "MAX_SERVICIOS_POR_POST", 2)
    crear_servicio(post.id, titulo="Uno")
    crear_servicio(post.id, titulo="Dos")

    client.post("/servicios/nuevo", data={
        "post_id": post.id, "titulo": "Tres", "rubro": Rubros.PLOMERIA,
    })

    assert Service.query.count() == 2


# --- listado publico en el detalle del emprendimiento

def test_el_visitante_ve_los_servicios_disponibles(
    client, crear_usuario, crear_post, crear_servicio
):
    autor = crear_usuario(username="autor")
    post = crear_post(autor.id)
    crear_servicio(post.id, titulo="Destapaciones", zona_cobertura="Maipú")

    html = client.get(f"/blog/{post.id}").get_data(as_text=True)

    assert "Destapaciones" in html
    assert "Maipú" in html


def test_un_servicio_no_disponible_no_le_llega_al_visitante(
    client, crear_usuario, crear_post, crear_servicio
):
    """El filtro va en la consulta y no en el template: si se filtrara al
    mostrar, el titulo igual viajaria en el HTML y se leeria en el fuente."""
    autor = crear_usuario(username="autor")
    post = crear_post(autor.id)
    crear_servicio(post.id, titulo="Servicio apagado", disponible=False)

    html = client.get(f"/blog/{post.id}").get_data(as_text=True)

    assert "Servicio apagado" not in html


def test_el_dueño_si_ve_sus_servicios_apagados(
    client, crear_usuario, crear_post, crear_servicio, login
):
    autor = crear_usuario(username="autor")
    post = crear_post(autor.id)
    crear_servicio(post.id, titulo="Servicio apagado", disponible=False)
    login(autor.id)

    html = client.get(f"/blog/{post.id}").get_data(as_text=True)

    assert "Servicio apagado" in html


def test_un_servicio_sin_precio_se_muestra_a_presupuestar(
    client, crear_usuario, crear_post, crear_servicio
):
    autor = crear_usuario(username="autor")
    post = crear_post(autor.id)
    crear_servicio(post.id, titulo="Instalación de termotanque")

    html = client.get(f"/blog/{post.id}").get_data(as_text=True)

    assert "A presupuestar" in html


def test_los_servicios_no_reemplazan_al_catalogo_de_productos(
    client, crear_usuario, crear_post, crear_servicio, db
):
    """Las dos secciones conviven: la de productos no se toco."""
    from decimal import Decimal as D

    from models.product import Product

    autor = crear_usuario(username="autor")
    post = crear_post(autor.id)
    db.session.add(Product(post_id=post.id, nombre="Caño de PVC", precio=D("1500.00")))
    db.session.commit()
    crear_servicio(post.id, titulo="Destapaciones")

    html = client.get(f"/blog/{post.id}").get_data(as_text=True)

    assert "Caño de PVC" in html
    assert "Destapaciones" in html
    assert "Qué vende" in html
    assert "Qué hace" in html


# --- busqueda publica por rubro y zona

def test_la_busqueda_no_pide_login(client, crear_usuario, crear_post, crear_servicio):
    """Encontrar un plomero tiene que poder hacerlo cualquiera, tenga cuenta o no."""
    autor = crear_usuario(username="autor")
    post = crear_post(autor.id)
    crear_servicio(post.id, titulo="Destapaciones")

    respuesta = client.get("/servicios/buscar")

    assert respuesta.status_code == 200
    assert "Destapaciones" in respuesta.get_data(as_text=True)


def test_la_busqueda_filtra_por_rubro(client, crear_usuario, crear_post, crear_servicio):
    autor = crear_usuario(username="autor")
    post = crear_post(autor.id)
    crear_servicio(post.id, titulo="Destapaciones", rubro=Rubros.PLOMERIA)
    crear_servicio(post.id, titulo="Cambio de tablero", rubro=Rubros.ELECTRICIDAD)

    html = client.get(f"/servicios/buscar?rubro={Rubros.PLOMERIA}").get_data(as_text=True)

    assert "Destapaciones" in html
    assert "Cambio de tablero" not in html


def test_la_busqueda_filtra_la_zona_sin_importar_mayusculas(
    client, crear_usuario, crear_post, crear_servicio
):
    """zona_cobertura es texto libre a proposito, asi que el filtro es ilike."""
    autor = crear_usuario(username="autor")
    post = crear_post(autor.id)
    crear_servicio(post.id, titulo="Destapaciones", zona_cobertura="Maipu y alrededores")
    crear_servicio(post.id, titulo="Cambio de tablero", zona_cobertura="Godoy Cruz")

    html = client.get("/servicios/buscar?zona=maipu").get_data(as_text=True)

    assert "Destapaciones" in html
    assert "Cambio de tablero" not in html


def test_la_busqueda_no_trata_el_guion_bajo_de_la_zona_como_comodin(
    client, crear_usuario, crear_post, crear_servicio
):
    """En un patron LIKE, _ significa "cualquier caracter".

    Sin escaparlo, buscar la zona "Maipu_centro" traia tambien "Maipu centro" y
    cualquier otra que solo se pareciera. El que escribe en el buscador espera
    que el guion bajo sea un guion bajo.
    """
    autor = crear_usuario(username="autor")
    post = crear_post(autor.id)
    crear_servicio(post.id, titulo="Destapaciones", zona_cobertura="Maipu_centro")
    crear_servicio(post.id, titulo="Cambio de tablero", zona_cobertura="Maipu centro")

    html = client.get("/servicios/buscar?zona=Maipu_centro").get_data(as_text=True)

    assert "Destapaciones" in html
    assert "Cambio de tablero" not in html


def test_la_busqueda_no_trata_el_porcentaje_de_la_zona_como_comodin(
    client, crear_usuario, crear_post, crear_servicio
):
    """El otro comodin: sin escapar, buscar "%" devolvia todo el catalogo."""
    autor = crear_usuario(username="autor")
    post = crear_post(autor.id)
    crear_servicio(post.id, titulo="Destapaciones", zona_cobertura="Godoy Cruz")

    html = client.get("/servicios/buscar?zona=%25").get_data(as_text=True)

    assert "Destapaciones" not in html


def test_la_busqueda_no_muestra_los_servicios_apagados(
    client, crear_usuario, crear_post, crear_servicio
):
    """Mismo criterio que el catalogo del emprendimiento: un servicio apagado no
    esta tomando trabajos, y el filtro va en la consulta y no en el template."""
    autor = crear_usuario(username="autor")
    post = crear_post(autor.id)
    crear_servicio(post.id, titulo="Servicio apagado", disponible=False)

    html = client.get("/servicios/buscar").get_data(as_text=True)

    assert "Servicio apagado" not in html


def test_un_rubro_que_no_existe_no_filtra_en_vez_de_romper(
    client, crear_usuario, crear_post, crear_servicio
):
    """Criterio permisivo, el mismo que usa el listado de emprendimientos con su
    categoria: la URL se escribe a mano y no por eso se corta con un 400."""
    autor = crear_usuario(username="autor")
    post = crear_post(autor.id)
    crear_servicio(post.id, titulo="Destapaciones")

    respuesta = client.get("/servicios/buscar?rubro=inventado")

    assert respuesta.status_code == 200
    assert "Destapaciones" in respuesta.get_data(as_text=True)


def test_la_busqueda_muestra_el_emprendimiento_que_lo_ofrece(
    client, crear_usuario, crear_post, crear_servicio
):
    autor = crear_usuario(username="autor")
    post = crear_post(autor.id, title="Plomería Central")
    crear_servicio(post.id, titulo="Destapaciones")

    html = client.get("/servicios/buscar").get_data(as_text=True)

    assert "Plomería Central" in html
    assert f'href="/blog/{post.id}"' in html


def test_el_visitante_sin_sesion_no_ve_el_boton_de_presupuesto(
    client, crear_usuario, crear_post, crear_servicio
):
    """solicitar() tiene @login_required y no vuelve al servicio despues del
    login: mostrar el boton igual mandaria al visitante a una pantalla de la que
    no puede volver a lo que estaba mirando. Mismo criterio que blog/detail.html
    con "Escribirle al emprendedor" y con el formulario de reseña."""
    autor = crear_usuario(username="autor")
    post = crear_post(autor.id)
    servicio = crear_servicio(post.id, titulo="Destapaciones")

    html = client.get("/servicios/buscar").get_data(as_text=True)

    assert "Destapaciones" in html
    assert f"/servicios/{servicio.id}/solicitar" not in html
    assert "iniciar sesión" in html


def test_el_visitante_logueado_si_ve_el_boton_de_presupuesto(
    client, crear_usuario, crear_post, crear_servicio, login
):
    autor = crear_usuario(username="autor")
    cliente = crear_usuario(username="cliente")
    post = crear_post(autor.id)
    servicio = crear_servicio(post.id, titulo="Destapaciones")
    login(cliente.id)

    html = client.get("/servicios/buscar").get_data(as_text=True)

    assert f"/servicios/{servicio.id}/solicitar" in html
    assert "Pedir presupuesto" in html


def test_la_busqueda_pagina(client, crear_usuario, crear_post, crear_servicio, app):
    """No trae todo con .all(): se rompe solo cuando el listado crece."""
    autor = crear_usuario(username="autor")
    post = crear_post(autor.id)
    por_pagina = app.config["POSTS_POR_PAGINA"]
    for numero in range(por_pagina + 1):
        crear_servicio(post.id, titulo=f"Trabajo {numero:02d}")

    primera = client.get("/servicios/buscar").get_data(as_text=True)
    segunda = client.get("/servicios/buscar?page=2").get_data(as_text=True)

    assert f"Trabajo {por_pagina:02d}" not in primera
    assert f"Trabajo {por_pagina:02d}" in segunda


def test_la_paginacion_no_pierde_los_filtros(
    client, crear_usuario, crear_post, crear_servicio, app
):
    autor = crear_usuario(username="autor")
    post = crear_post(autor.id)
    for numero in range(app.config["POSTS_POR_PAGINA"] + 1):
        crear_servicio(post.id, titulo=f"Trabajo {numero:02d}", rubro=Rubros.PLOMERIA)

    html = client.get(f"/servicios/buscar?rubro={Rubros.PLOMERIA}").get_data(as_text=True)

    assert f"rubro={Rubros.PLOMERIA}" in html
    assert "page=2" in html


# --- solicitudes de presupuesto

@pytest.fixture
def crear_solicitud(db):
    """Fabrica de solicitudes de presupuesto."""

    def _crear(service_id, cliente_id, descripcion="Se me tapó la pileta",
               zona=None, foto=None, estado=EstadosSolicitud.PENDIENTE,
               respuesta_precio=None, respuesta_mensaje=None):
        solicitud = ServiceRequest(
            service_id=service_id, cliente_id=cliente_id,
            descripcion=descripcion, zona=zona, foto=foto, estado=estado,
            respuesta_precio=(
                Decimal(respuesta_precio) if respuesta_precio is not None else None
            ),
            respuesta_mensaje=respuesta_mensaje,
        )
        db.session.add(solicitud)
        db.session.commit()
        return solicitud

    return _crear


@pytest.fixture
def servicio_y_cliente(crear_usuario, crear_post, crear_servicio, login):
    """Un servicio de un emprendedor y un cliente logueado que no es el dueño."""

    def _crear():
        prestador = crear_usuario(username="prestador")
        post = crear_post(prestador.id)
        servicio = crear_servicio(post.id, titulo="Destapaciones")
        cliente = crear_usuario(username="cliente")
        login(cliente.id)
        return prestador, servicio, cliente

    return _crear


def test_un_cliente_puede_pedir_presupuesto(client, servicio_y_cliente):
    _prestador, servicio, cliente = servicio_y_cliente()

    respuesta = client.post(f"/servicios/{servicio.id}/solicitar", data={
        "descripcion": "Se me tapó la cocina", "zona": "Coquimbito",
    })

    assert respuesta.status_code == 302
    solicitud = ServiceRequest.query.one()
    assert solicitud.cliente_id == cliente.id
    assert solicitud.service_id == servicio.id
    assert solicitud.zona == "Coquimbito"
    assert solicitud.estado == EstadosSolicitud.PENDIENTE
    assert solicitud.responded_at is None


def test_una_solicitud_sin_descripcion_no_se_guarda(client, servicio_y_cliente):
    _prestador, servicio, _cliente = servicio_y_cliente()

    respuesta = client.post(f"/servicios/{servicio.id}/solicitar", data={"descripcion": ""})

    assert respuesta.status_code == 200  # vuelve al formulario
    assert ServiceRequest.query.count() == 0


def test_no_se_puede_pedir_presupuesto_dos_veces_sobre_lo_mismo(
    client, servicio_y_cliente
):
    """El caso del doble click: sin esto quedan dos solicitudes iguales."""
    _prestador, servicio, _cliente = servicio_y_cliente()
    datos = {"descripcion": "Se me tapó la cocina"}

    client.post(f"/servicios/{servicio.id}/solicitar", data=datos)
    client.post(f"/servicios/{servicio.id}/solicitar", data=datos)

    assert ServiceRequest.query.count() == 1


def test_se_puede_volver_a_pedir_cuando_la_anterior_ya_no_esta_pendiente(
    client, servicio_y_cliente, crear_solicitud
):
    """El freno es a las pendientes, no al cliente: el mismo problema puede
    volver a pasar el año que viene."""
    _prestador, servicio, cliente = servicio_y_cliente()
    crear_solicitud(servicio.id, cliente.id, estado=EstadosSolicitud.CERRADA)

    client.post(f"/servicios/{servicio.id}/solicitar", data={"descripcion": "Otra vez"})

    assert ServiceRequest.query.count() == 2


# --- una sola pendiente: la constraint, no el chequeo

def test_la_base_rechaza_dos_pendientes_del_mismo_cliente_y_servicio(
    db, servicio_y_cliente, crear_solicitud
):
    """El freno tiene que estar en la base y no solo en la vista: es lo unico
    que no se puede saltear metiendo dos requests a la vez."""
    _prestador, servicio, cliente = servicio_y_cliente()
    crear_solicitud(servicio.id, cliente.id)

    with pytest.raises(IntegrityError):
        crear_solicitud(servicio.id, cliente.id, descripcion="La misma otra vez")

    db.session.rollback()


@pytest.mark.parametrize("estado", [EstadosSolicitud.RESPONDIDA, EstadosSolicitud.CERRADA])
def test_la_constraint_no_toca_las_que_ya_no_estan_pendientes(
    servicio_y_cliente, crear_solicitud, estado
):
    """El UNIQUE es sobre cupo_pendiente, que solo tiene valor mientras la
    solicitud esta pendiente: de las otras puede haber todas las que sea."""
    _prestador, servicio, cliente = servicio_y_cliente()
    crear_solicitud(servicio.id, cliente.id, estado=estado)
    crear_solicitud(servicio.id, cliente.id, descripcion="Otra", estado=estado)

    assert ServiceRequest.query.count() == 2


def test_responder_libera_el_cupo_para_un_pedido_nuevo(
    client, servicio_y_cliente, crear_solicitud, login
):
    """El cupo lo mantiene el listener del modelo, asi que tiene que soltarse
    solo cuando la solicitud cambia de estado, sin que nadie lo toque."""
    prestador, servicio, cliente = servicio_y_cliente()
    solicitud = crear_solicitud(servicio.id, cliente.id)
    login(prestador.id)
    client.post(f"/servicios/solicitudes/{solicitud.id}/responder", data={
        "respuesta_precio": "", "respuesta_mensaje": "Puedo el martes.",
    })

    login(cliente.id)
    client.post(f"/servicios/{servicio.id}/solicitar", data={"descripcion": "Otra cosa"})

    assert ServiceRequest.query.count() == 2
    assert ServiceRequest.query.filter_by(
        estado=EstadosSolicitud.PENDIENTE
    ).count() == 1


def test_otra_violacion_de_integridad_no_se_disfraza_de_pendiente_duplicada(
    client, db, servicio_y_cliente, monkeypatch
):
    """El INSERT puede fallar por otra cosa: aca el prestador borra el servicio
    justo entre el chequeo y el INSERT, y lo que salta es la FK.

    Ese error no puede terminar en "ya tenés una solicitud pendiente", que
    ademas de ser mentira taparia el problema real sin dejar rastro.
    """
    from app.servicios import vistas

    _prestador, servicio, _cliente = servicio_y_cliente()
    servicio_id = servicio.id

    def _borrar_el_servicio_en_el_medio(service_id, cliente_id):
        db.session.execute(
            db.text("DELETE FROM services WHERE id = :id"), {"id": service_id}
        )
        return None

    monkeypatch.setattr(vistas, "solicitud_pendiente_de", _borrar_el_servicio_en_el_medio)

    with pytest.raises(IntegrityError):
        client.post(f"/servicios/{servicio_id}/solicitar", data={"descripcion": "Hola"})

    db.session.rollback()
    assert ServiceRequest.query.count() == 0


def test_dos_pedidos_simultaneos_dejan_una_sola_pendiente(tmp_path, monkeypatch):
    """La carrera de verdad, con dos hilos y una Barrier.

    Postear dos veces seguidas no prueba nada de esto: lo ataja el chequeo de
    la vista. El bug esta en la ventana entre ese SELECT y el INSERT, asi que
    la barrera se pone justo ahi, envolviendo _solicitud_pendiente_de: los dos
    hilos ven "no hay ninguna pendiente" y recien despues insertan los dos.

    Va sobre una base en un archivo y no sobre la de memoria de conftest,
    porque en SQLite la base ":memory:" vive en una sola conexion y no hay dos
    requests concurrentes que valgan.
    """
    from app.servicios import vistas
    from config import TestingConfig

    monkeypatch.setattr(
        TestingConfig, "SQLALCHEMY_DATABASE_URI",
        f"sqlite:///{tmp_path / 'concurrencia.sqlite'}",
    )
    app = create_app("testing")

    with app.app_context():
        _db.create_all()
        prestador = User(username="prestador", email="prestador@test.com", password="x")
        cliente = User(username="cliente", email="cliente@test.com", password="x")
        _db.session.add_all([prestador, cliente])
        _db.session.commit()
        post = Post(author=prestador.id, title="Lo mío", body="Plomería")
        _db.session.add(post)
        _db.session.commit()
        servicio = Service(post_id=post.id, titulo="Destapaciones", rubro=Rubros.PLOMERIA)
        _db.session.add(servicio)
        _db.session.commit()
        servicio_id, cliente_id = servicio.id, cliente.id

    barrera = threading.Barrier(2, timeout=10)
    chequeo_original = vistas.solicitud_pendiente_de
    # Solo se espera en el chequeo de la ida. El que pierde la carrera vuelve a
    # preguntar por la pendiente al manejar el IntegrityError, y ahi ya no hay
    # nadie del otro lado esperando.
    ida = threading.local()

    def _chequear_y_esperar(service_id, cliente_id_):
        pendiente = chequeo_original(service_id, cliente_id_)
        if not getattr(ida, "cumplida", False):
            ida.cumplida = True
            # Los dos hilos ya hicieron el SELECT; salen juntos a insertar.
            barrera.wait()
        return pendiente

    monkeypatch.setattr(vistas, "solicitud_pendiente_de", _chequear_y_esperar)

    respuestas = {}
    fallas = {}

    def pedir(numero):
        try:
            navegador = app.test_client()
            with navegador.session_transaction() as sesion:
                sesion["user_id"] = cliente_id
            respuestas[numero] = navegador.post(
                f"/servicios/{servicio_id}/solicitar",
                data={"descripcion": f"Se me tapó todo ({numero})"},
            )
        except Exception as e:  # noqa: BLE001 - se reporta abajo, en el assert
            fallas[numero] = e

    hilos = [threading.Thread(target=pedir, args=(numero,)) for numero in (1, 2)]
    for hilo in hilos:
        hilo.start()
    for hilo in hilos:
        hilo.join(timeout=30)

    assert not fallas, f"algun request exploto: {fallas}"
    # Ninguno de los dos ve un error: el que pierde la carrera termina en la
    # solicitud que si quedo, igual que si hubiera llegado un rato despues.
    assert [r.status_code for r in respuestas.values()] == [302, 302]

    with app.app_context():
        assert ServiceRequest.query.filter_by(
            service_id=servicio_id, cliente_id=cliente_id,
            estado=EstadosSolicitud.PENDIENTE,
        ).count() == 1
        _db.session.remove()
        _db.engine.dispose()


def test_el_dueño_no_se_pide_presupuesto_a_si_mismo(
    client, crear_usuario, crear_post, crear_servicio, login
):
    prestador = crear_usuario(username="prestador")
    post = crear_post(prestador.id)
    servicio = crear_servicio(post.id)
    login(prestador.id)

    respuesta = client.post(f"/servicios/{servicio.id}/solicitar", data={
        "descripcion": "Me pido a mí mismo",
    })

    assert respuesta.status_code == 302
    assert ServiceRequest.query.count() == 0


def test_no_se_puede_pedir_presupuesto_de_un_servicio_apagado(
    client, crear_usuario, crear_post, crear_servicio, login
):
    """El link no se muestra, pero se puede escribir a mano."""
    prestador = crear_usuario(username="prestador")
    post = crear_post(prestador.id)
    servicio = crear_servicio(post.id, disponible=False)
    cliente = crear_usuario(username="cliente")
    login(cliente.id)

    respuesta = client.post(f"/servicios/{servicio.id}/solicitar", data={
        "descripcion": "Hola",
    })

    assert respuesta.status_code == 302
    assert ServiceRequest.query.count() == 0


def test_pedir_presupuesto_sin_sesion_manda_al_login(
    client, crear_usuario, crear_post, crear_servicio
):
    prestador = crear_usuario(username="prestador")
    servicio = crear_servicio(crear_post(prestador.id).id)

    respuesta = client.get(f"/servicios/{servicio.id}/solicitar")

    assert respuesta.status_code == 302
    assert "/auth/login" in respuesta.headers["Location"]


# --- privacidad de las solicitudes

def test_el_cliente_ve_su_solicitud(client, servicio_y_cliente, crear_solicitud):
    _prestador, servicio, cliente = servicio_y_cliente()
    solicitud = crear_solicitud(servicio.id, cliente.id, descripcion="Se me tapó todo")

    respuesta = client.get(f"/servicios/solicitudes/{solicitud.id}")

    assert respuesta.status_code == 200
    assert "Se me tapó todo" in respuesta.get_data(as_text=True)


def test_el_prestador_ve_la_solicitud_que_recibio(
    client, servicio_y_cliente, crear_solicitud, login
):
    prestador, servicio, cliente = servicio_y_cliente()
    solicitud = crear_solicitud(servicio.id, cliente.id, descripcion="Se me tapó todo")
    login(prestador.id)

    respuesta = client.get(f"/servicios/solicitudes/{solicitud.id}")

    assert respuesta.status_code == 200
    assert "Se me tapó todo" in respuesta.get_data(as_text=True)


def test_un_tercero_no_ve_la_solicitud(
    client, servicio_y_cliente, crear_solicitud, crear_usuario, login
):
    """Ni el contenido ni un 200: se chequea sobre el HTML servido, no sobre
    lo que se muestre en pantalla."""
    _prestador, servicio, cliente = servicio_y_cliente()
    solicitud = crear_solicitud(servicio.id, cliente.id, descripcion="Se me tapó todo")
    curioso = crear_usuario(username="curioso")
    login(curioso.id)

    respuesta = client.get(f"/servicios/solicitudes/{solicitud.id}")

    assert respuesta.status_code == 403
    assert "Se me tapó todo" not in respuesta.get_data(as_text=True)


def test_otro_emprendedor_tampoco_ve_la_solicitud(
    client, servicio_y_cliente, crear_solicitud, crear_usuario, crear_post, login
):
    """Explicito porque es el caso que mas se presta a confusion: tener un
    emprendimiento no da acceso a los pedidos de los demas."""
    _prestador, servicio, cliente = servicio_y_cliente()
    solicitud = crear_solicitud(servicio.id, cliente.id, descripcion="Se me tapó todo")
    otro = crear_usuario(username="otro")
    crear_post(otro.id, title="Otro emprendimiento")
    login(otro.id)

    respuesta = client.get(f"/servicios/solicitudes/{solicitud.id}")

    assert respuesta.status_code == 403
    assert "Se me tapó todo" not in respuesta.get_data(as_text=True)


def test_sin_sesion_la_solicitud_no_se_ve(
    client, servicio_y_cliente, crear_solicitud
):
    _prestador, servicio, cliente = servicio_y_cliente()
    solicitud = crear_solicitud(servicio.id, cliente.id, descripcion="Se me tapó todo")
    client.get("/auth/logout")

    respuesta = client.get(f"/servicios/solicitudes/{solicitud.id}")

    assert respuesta.status_code == 302
    assert "Se me tapó todo" not in respuesta.get_data(as_text=True)


# --- responder y cerrar

def test_el_prestador_responde_con_precio_y_mensaje(
    client, servicio_y_cliente, crear_solicitud, login
):
    prestador, servicio, cliente = servicio_y_cliente()
    solicitud = crear_solicitud(servicio.id, cliente.id)
    login(prestador.id)

    client.post(f"/servicios/solicitudes/{solicitud.id}/responder", data={
        "respuesta_precio": "25.000,50",
        "respuesta_mensaje": "Puedo ir el martes a la mañana.",
    })

    db_solicitud = ServiceRequest.query.one()
    assert db_solicitud.estado == EstadosSolicitud.RESPONDIDA
    assert db_solicitud.respuesta_precio == Decimal("25000.50")
    assert db_solicitud.respuesta_mensaje == "Puedo ir el martes a la mañana."
    assert db_solicitud.responded_at is not None


def test_se_puede_responder_sin_precio(
    client, servicio_y_cliente, crear_solicitud, login
):
    """"Pasame una foto" o "no llego a esa zona" son respuestas validas."""
    prestador, servicio, cliente = servicio_y_cliente()
    solicitud = crear_solicitud(servicio.id, cliente.id)
    login(prestador.id)

    client.post(f"/servicios/solicitudes/{solicitud.id}/responder", data={
        "respuesta_precio": "", "respuesta_mensaje": "¿Me pasás una foto?",
    })

    db_solicitud = ServiceRequest.query.one()
    assert db_solicitud.estado == EstadosSolicitud.RESPONDIDA
    assert db_solicitud.respuesta_precio is None


def test_no_se_puede_responder_sin_mensaje(
    client, servicio_y_cliente, crear_solicitud, login
):
    """Sin precio si, sin decir nada no."""
    prestador, servicio, cliente = servicio_y_cliente()
    solicitud = crear_solicitud(servicio.id, cliente.id)
    login(prestador.id)

    client.post(f"/servicios/solicitudes/{solicitud.id}/responder", data={
        "respuesta_precio": "1500", "respuesta_mensaje": "   ",
    })

    assert ServiceRequest.query.one().estado == EstadosSolicitud.PENDIENTE


def test_el_cliente_no_puede_responder_su_propia_solicitud(
    client, servicio_y_cliente, crear_solicitud
):
    """Es parte de la solicitud y la ve, pero la respuesta es del otro lado."""
    _prestador, servicio, cliente = servicio_y_cliente()
    solicitud = crear_solicitud(servicio.id, cliente.id)

    client.post(f"/servicios/solicitudes/{solicitud.id}/responder", data={
        "respuesta_mensaje": "Me contesto solo", "respuesta_precio": "1",
    })

    assert ServiceRequest.query.one().estado == EstadosSolicitud.PENDIENTE


def test_un_tercero_no_puede_responder(
    client, servicio_y_cliente, crear_solicitud, crear_usuario, login
):
    _prestador, servicio, cliente = servicio_y_cliente()
    solicitud = crear_solicitud(servicio.id, cliente.id)
    curioso = crear_usuario(username="curioso")
    login(curioso.id)

    respuesta = client.post(f"/servicios/solicitudes/{solicitud.id}/responder", data={
        "respuesta_mensaje": "Hola", "respuesta_precio": "1",
    })

    assert respuesta.status_code == 403
    assert ServiceRequest.query.one().estado == EstadosSolicitud.PENDIENTE


@pytest.mark.parametrize("quien", ["cliente", "prestador"])
def test_la_cierra_cualquiera_de_las_dos_partes(
    client, servicio_y_cliente, crear_solicitud, login, quien
):
    prestador, servicio, cliente = servicio_y_cliente()
    solicitud = crear_solicitud(servicio.id, cliente.id)
    login(prestador.id if quien == "prestador" else cliente.id)

    client.post(f"/servicios/solicitudes/{solicitud.id}/cerrar")

    assert ServiceRequest.query.one().estado == EstadosSolicitud.CERRADA


def test_un_tercero_no_puede_cerrarla(
    client, servicio_y_cliente, crear_solicitud, crear_usuario, login
):
    _prestador, servicio, cliente = servicio_y_cliente()
    solicitud = crear_solicitud(servicio.id, cliente.id)
    curioso = crear_usuario(username="curioso")
    login(curioso.id)

    respuesta = client.post(f"/servicios/solicitudes/{solicitud.id}/cerrar")

    assert respuesta.status_code == 403
    assert ServiceRequest.query.one().estado == EstadosSolicitud.PENDIENTE


def test_una_solicitud_cerrada_ya_no_se_responde(
    client, servicio_y_cliente, crear_solicitud, login
):
    """Cerrada es el final: no vuelve atras. Si hace falta seguir, se pide de
    nuevo (y ahi el freno de la pendiente ya no aplica)."""
    prestador, servicio, cliente = servicio_y_cliente()
    solicitud = crear_solicitud(servicio.id, cliente.id, estado=EstadosSolicitud.CERRADA)
    login(prestador.id)

    client.post(f"/servicios/solicitudes/{solicitud.id}/responder", data={
        "respuesta_mensaje": "Tarde", "respuesta_precio": "1500",
    })

    db_solicitud = ServiceRequest.query.one()
    assert db_solicitud.estado == EstadosSolicitud.CERRADA
    assert db_solicitud.respuesta_mensaje is None


def test_responder_y_cerrar_no_se_disparan_con_un_get(
    client, servicio_y_cliente, crear_solicitud, login
):
    prestador, servicio, cliente = servicio_y_cliente()
    solicitud = crear_solicitud(servicio.id, cliente.id)
    login(prestador.id)

    assert client.get(f"/servicios/solicitudes/{solicitud.id}/responder").status_code == 405
    assert client.get(f"/servicios/solicitudes/{solicitud.id}/cerrar").status_code == 405
    assert ServiceRequest.query.one().estado == EstadosSolicitud.PENDIENTE


# --- panel de solicitudes

def test_el_panel_muestra_las_recibidas_y_las_enviadas(
    client, crear_usuario, crear_post, crear_servicio, crear_solicitud, login
):
    """Un usuario puede ser las dos cosas: presta un servicio y pide otro."""
    yo = crear_usuario(username="yo")
    mi_servicio = crear_servicio(crear_post(yo.id, title="Lo mío").id, titulo="Lo que hago")
    otro = crear_usuario(username="otro")
    servicio_ajeno = crear_servicio(
        crear_post(otro.id, title="Lo de otro").id, titulo="Lo que hace el otro"
    )
    crear_solicitud(mi_servicio.id, otro.id, descripcion="Pedido que recibí")
    crear_solicitud(servicio_ajeno.id, yo.id, descripcion="Pedido que hice")
    login(yo.id)

    html = client.get("/servicios/solicitudes").get_data(as_text=True)

    assert "Pedido que recibí" in html
    assert "Pedido que hice" in html


def test_el_panel_no_muestra_solicitudes_de_terceros(
    client, servicio_y_cliente, crear_solicitud, crear_usuario, login
):
    _prestador, servicio, cliente = servicio_y_cliente()
    crear_solicitud(servicio.id, cliente.id, descripcion="Pedido ajeno")
    curioso = crear_usuario(username="curioso")
    login(curioso.id)

    html = client.get("/servicios/solicitudes").get_data(as_text=True)

    assert "Pedido ajeno" not in html


# --- badge del navbar

def test_el_badge_cuenta_las_solicitudes_pendientes(
    client, servicio_y_cliente, crear_solicitud, login
):
    prestador, servicio, cliente = servicio_y_cliente()
    crear_solicitud(servicio.id, cliente.id)
    login(prestador.id)

    datos = client.get("/mensajes/notificaciones").get_json()

    assert datos["pending_service_requests"] == 1
    assert datos["total"] == 1


def test_el_badge_no_cuenta_las_ya_respondidas(
    client, servicio_y_cliente, crear_solicitud, login
):
    """Una vez contestada, la pelota esta del otro lado."""
    prestador, servicio, cliente = servicio_y_cliente()
    crear_solicitud(servicio.id, cliente.id, estado=EstadosSolicitud.RESPONDIDA)
    crear_solicitud(
        servicio.id, cliente.id, descripcion="Otra", estado=EstadosSolicitud.CERRADA
    )
    login(prestador.id)

    datos = client.get("/mensajes/notificaciones").get_json()

    assert datos["pending_service_requests"] == 0
    assert datos["total"] == 0


def test_el_badge_no_le_cuenta_al_cliente_lo_que_pidio(
    client, servicio_y_cliente, crear_solicitud
):
    """El contador es de lo que espera una respuesta TUYA."""
    _prestador, servicio, cliente = servicio_y_cliente()
    crear_solicitud(servicio.id, cliente.id)

    datos = client.get("/mensajes/notificaciones").get_json()

    assert datos["pending_service_requests"] == 0


# --- borrados en cascada de las solicitudes

def test_borrar_el_servicio_se_lleva_sus_solicitudes(
    db, servicio_y_cliente, crear_solicitud
):
    _prestador, servicio, cliente = servicio_y_cliente()
    crear_solicitud(servicio.id, cliente.id)

    db.session.delete(servicio)
    db.session.commit()

    assert ServiceRequest.query.count() == 0


def test_borrar_el_cliente_se_lleva_sus_solicitudes(
    db, servicio_y_cliente, crear_solicitud
):
    """La FK a users nace con ON DELETE CASCADE, a diferencia de las cinco
    viejas que todavia traban el borrado de un usuario (ver B1)."""
    _prestador, servicio, cliente = servicio_y_cliente()
    crear_solicitud(servicio.id, cliente.id)

    db.session.delete(cliente)
    db.session.commit()

    assert ServiceRequest.query.count() == 0


def test_borrar_el_emprendimiento_se_lleva_servicios_y_solicitudes(
    db, servicio_y_cliente, crear_solicitud
):
    _prestador, servicio, cliente = servicio_y_cliente()
    crear_solicitud(servicio.id, cliente.id)
    post = servicio.post

    db.session.delete(post)
    db.session.commit()

    assert Service.query.count() == 0
    assert ServiceRequest.query.count() == 0


def test_servicios_esta_en_los_slugs_reservados():
    """/servicios es una ruta de primer nivel: un usuario con ese slug no la
    tapa hoy (el perfil vive bajo /perfil/), pero se reserva igual, con el
    mismo criterio que "blog", "mensajes", "favoritos" y "eventos"."""
    from services.slugs import SLUGS_RESERVADOS

    assert "servicios" in SLUGS_RESERVADOS


# --- verificacion de credenciales

@pytest.fixture
def uploads_temporales(app, tmp_path):
    """Manda los uploads del test a una carpeta descartable.

    Sin esto, subir el documento en un test escribe en la carpeta real del repo
    y deja el archivo ahi despues de que el test termina.

    Se apuntan las DOS carpetas: el documento de verificacion va a la privada
    (ver PRIVATE_UPLOAD_FOLDER), pero dejar la publica sin redirigir haria que
    cualquier test que suba otra cosa siga ensuciando static/uploads.
    """
    app.config["UPLOAD_FOLDER"] = str(tmp_path / "publico")
    app.config["PRIVATE_UPLOAD_FOLDER"] = str(tmp_path / "privado")
    return tmp_path / "privado"


def _documento(nombre="matricula.png"):
    """Un archivo de imagen valido, listo para subir en un multipart."""
    import io

    from PIL import Image
    from werkzeug.datastructures import FileStorage

    buffer = io.BytesIO()
    Image.new("RGB", (10, 10), "green").save(buffer, format="PNG")
    buffer.seek(0)
    return FileStorage(stream=buffer, filename=nombre, content_type="image/png")


@pytest.fixture
def crear_verificacion(db):
    """Fabrica de pedidos de verificacion."""

    def _crear(service_id, estado=EstadosVerificacion.PENDIENTE, foto="doc.png",
               motivo_rechazo=None):
        verificacion = VerificationRequest(
            service_id=service_id, foto=foto, estado=estado,
            motivo_rechazo=motivo_rechazo,
        )
        db.session.add(verificacion)
        db.session.commit()
        return verificacion

    return _crear


def test_un_servicio_nace_sin_verificar(db, crear_usuario, crear_post, crear_servicio):
    """El sello no es un default: alguien lo tiene que mirar."""
    autor = crear_usuario(username="autor")
    post = crear_post(autor.id)
    servicio = crear_servicio(post.id)
    db.session.expire_all()

    assert db.session.get(Service, servicio.id).verificado is False


def test_el_dueño_no_puede_marcarse_verificado_desde_el_formulario(
    db, client, emprendedor_con_post, crear_servicio
):
    """Si el dueño pudiera marcarlo, el sello no significaria nada. El campo no
    entra por formulario.leer_servicio(), asi que mandarlo a mano no hace nada."""
    _usuario, post = emprendedor_con_post()
    servicio = crear_servicio(post.id, titulo="Instalaciones de gas")

    client.post(f"/servicios/{servicio.id}/editar", data={
        "post_id": post.id, "titulo": "Instalaciones de gas",
        "rubro": Rubros.GAS, "descripcion": "", "zona_cobertura": "",
        "precio_estimado": "", "disponible": "on", "verificado": "on",
    })

    db.session.refresh(servicio)
    assert servicio.verificado is False


def test_pedir_verificacion_guarda_el_pedido_con_la_foto(
    db, client, emprendedor_con_post, crear_servicio, uploads_temporales
):
    _usuario, post = emprendedor_con_post()
    servicio = crear_servicio(post.id)

    client.post(
        f"/servicios/{servicio.id}/verificar",
        data={"foto": _documento()},
        content_type="multipart/form-data",
    )

    pedido = VerificationRequest.query.one()
    assert pedido.service_id == servicio.id
    assert pedido.estado == EstadosVerificacion.PENDIENTE
    assert pedido.foto
    assert (uploads_temporales / pedido.foto).exists()
    # El pedido no verifica nada por si solo: eso lo decide el admin.
    db.session.refresh(servicio)
    assert servicio.verificado is False


def test_pedir_verificacion_sin_foto_no_guarda_nada(
    client, emprendedor_con_post, crear_servicio, uploads_temporales
):
    """save_post_image devuelve (None, None) sin archivo, que para el resto del
    proyecto no es un error. Aca si: sin documento no hay nada que revisar."""
    _usuario, post = emprendedor_con_post()
    servicio = crear_servicio(post.id)

    respuesta = client.post(
        f"/servicios/{servicio.id}/verificar",
        data={}, content_type="multipart/form-data",
    )

    assert VerificationRequest.query.count() == 0
    assert "matrícula" in respuesta.get_data(as_text=True)


def test_no_se_puede_pedir_verificacion_de_un_servicio_ajeno(
    client, crear_usuario, crear_post, crear_servicio, login, uploads_temporales
):
    """Sin esto, un tercero llena la cola del admin con documentos de servicios
    que no son suyos. Mismo _servicio_propio que el resto del ABM."""
    autor = crear_usuario(username="autor")
    intruso = crear_usuario(username="intruso")
    post = crear_post(autor.id)
    servicio = crear_servicio(post.id)
    login(intruso.id)

    client.post(
        f"/servicios/{servicio.id}/verificar",
        data={"foto": _documento()},
        content_type="multipart/form-data",
    )

    assert VerificationRequest.query.count() == 0


def test_no_se_puede_pedir_verificacion_dos_veces(
    client, emprendedor_con_post, crear_servicio, crear_verificacion,
    uploads_temporales
):
    """Ya hay una esperando: se muestra eso en vez del formulario."""
    _usuario, post = emprendedor_con_post()
    servicio = crear_servicio(post.id)
    crear_verificacion(servicio.id)

    client.post(
        f"/servicios/{servicio.id}/verificar",
        data={"foto": _documento()},
        content_type="multipart/form-data",
    )

    assert VerificationRequest.query.count() == 1


def test_la_base_frena_la_segunda_pendiente_aunque_la_vista_no_mire(
    db, crear_usuario, crear_post, crear_servicio, crear_verificacion
):
    """El freno de verdad es el UNIQUE, no el chequeo de la vista: entre el
    SELECT y el INSERT hay una ventana por la que pasan dos requests juntos."""
    autor = crear_usuario(username="autor")
    post = crear_post(autor.id)
    servicio = crear_servicio(post.id)
    crear_verificacion(servicio.id)

    db.session.add(VerificationRequest(service_id=servicio.id, foto="otra.png"))
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


def test_despues_de_un_rechazo_se_puede_volver_a_pedir(
    db, crear_usuario, crear_post, crear_servicio, crear_verificacion
):
    """Justamente por esto la constraint lleva la columna centinela y no es un
    UNIQUE(service_id) a secas, que prohibiria el segundo intento para siempre."""
    autor = crear_usuario(username="autor")
    post = crear_post(autor.id)
    servicio = crear_servicio(post.id)
    crear_verificacion(servicio.id, estado=EstadosVerificacion.RECHAZADA)

    db.session.add(VerificationRequest(service_id=servicio.id, foto="segunda.png"))
    db.session.commit()

    assert VerificationRequest.query.count() == 2


def test_resolver_un_pedido_libera_el_cupo(
    db, crear_usuario, crear_post, crear_servicio, crear_verificacion
):
    """cupo_pendiente lo mantiene el listener, no las vistas."""
    autor = crear_usuario(username="autor")
    post = crear_post(autor.id)
    servicio = crear_servicio(post.id)
    verificacion = crear_verificacion(servicio.id)

    assert verificacion.cupo_pendiente == 1

    verificacion.estado = EstadosVerificacion.APROBADA
    db.session.commit()

    assert verificacion.cupo_pendiente is None


def test_borrar_un_servicio_se_lleva_sus_verificaciones(
    db, crear_usuario, crear_post, crear_servicio, crear_verificacion
):
    autor = crear_usuario(username="autor")
    post = crear_post(autor.id)
    servicio = crear_servicio(post.id)
    crear_verificacion(servicio.id)

    db.session.delete(servicio)
    db.session.commit()

    assert VerificationRequest.query.count() == 0


# --- verificacion: el lado del admin

def test_un_usuario_comun_no_ve_la_cola_de_verificaciones(client, crear_usuario, login):
    usuario = crear_usuario(username="tomy")
    login(usuario.id)

    assert client.get("/admin/verificaciones").status_code == 403


def test_el_admin_aprueba_y_el_servicio_queda_verificado(
    db, client, crear_usuario, crear_post, crear_servicio, crear_verificacion, login
):
    admin = crear_usuario(username="jefa", rol=Roles.ADMIN)
    autor = crear_usuario(username="autor")
    post = crear_post(autor.id)
    servicio = crear_servicio(post.id)
    verificacion = crear_verificacion(servicio.id)
    login(admin.id)

    client.post(f"/admin/verificaciones/{verificacion.id}/aprobar")

    db.session.refresh(servicio)
    db.session.refresh(verificacion)
    assert servicio.verificado is True
    assert verificacion.estado == EstadosVerificacion.APROBADA
    assert verificacion.resuelto_at is not None


def test_el_admin_rechaza_con_motivo_y_no_toca_el_sello(
    db, client, crear_usuario, crear_post, crear_servicio, crear_verificacion, login
):
    """Un rechazo puede ser que la foto salio movida: no verifica, pero tampoco
    saca un sello que ya estaba."""
    admin = crear_usuario(username="jefa", rol=Roles.ADMIN)
    autor = crear_usuario(username="autor")
    post = crear_post(autor.id)
    servicio = crear_servicio(post.id)
    verificacion = crear_verificacion(servicio.id)
    login(admin.id)

    client.post(
        f"/admin/verificaciones/{verificacion.id}/rechazar",
        data={"motivo_rechazo": "La foto no se lee."},
    )

    db.session.refresh(servicio)
    db.session.refresh(verificacion)
    assert servicio.verificado is False
    assert verificacion.estado == EstadosVerificacion.RECHAZADA
    assert verificacion.motivo_rechazo == "La foto no se lee."


def test_rechazar_sin_motivo_deja_la_columna_en_null(
    db, client, crear_usuario, crear_post, crear_servicio, crear_verificacion, login
):
    """None y no cadena vacia: la columna es nullable justamente para poder
    distinguir que el admin no dijo por que."""
    admin = crear_usuario(username="jefa", rol=Roles.ADMIN)
    autor = crear_usuario(username="autor")
    post = crear_post(autor.id)
    servicio = crear_servicio(post.id)
    verificacion = crear_verificacion(servicio.id)
    login(admin.id)

    client.post(f"/admin/verificaciones/{verificacion.id}/rechazar", data={})

    db.session.refresh(verificacion)
    assert verificacion.motivo_rechazo is None


def test_un_pedido_ya_resuelto_no_se_vuelve_a_resolver(
    db, client, crear_usuario, crear_post, crear_servicio, crear_verificacion, login
):
    """El segundo POST (otro admin, o la misma pestaña abierta dos veces) no
    tiene que dar vuelta la decision del primero."""
    admin = crear_usuario(username="jefa", rol=Roles.ADMIN)
    autor = crear_usuario(username="autor")
    post = crear_post(autor.id)
    servicio = crear_servicio(post.id)
    verificacion = crear_verificacion(servicio.id, estado=EstadosVerificacion.RECHAZADA)
    login(admin.id)

    client.post(f"/admin/verificaciones/{verificacion.id}/aprobar")

    db.session.refresh(servicio)
    db.session.refresh(verificacion)
    assert servicio.verificado is False
    assert verificacion.estado == EstadosVerificacion.RECHAZADA


def test_la_cola_del_admin_solo_trae_las_pendientes(
    client, crear_usuario, crear_post, crear_servicio, crear_verificacion, login
):
    admin = crear_usuario(username="jefa", rol=Roles.ADMIN)
    autor = crear_usuario(username="autor")
    post = crear_post(autor.id)
    pendiente = crear_servicio(post.id, titulo="Instalación de gas")
    resuelto = crear_servicio(post.id, titulo="Cambio de tablero")
    crear_verificacion(pendiente.id)
    crear_verificacion(resuelto.id, estado=EstadosVerificacion.APROBADA)
    login(admin.id)

    html = client.get("/admin/verificaciones").get_data(as_text=True)

    assert "Instalación de gas" in html
    assert "Cambio de tablero" not in html


def test_el_dashboard_cuenta_las_verificaciones_pendientes(
    client, crear_usuario, crear_post, crear_servicio, crear_verificacion, login
):
    admin = crear_usuario(username="jefa", rol=Roles.ADMIN)
    autor = crear_usuario(username="autor")
    post = crear_post(autor.id)
    servicio = crear_servicio(post.id)
    crear_verificacion(servicio.id)
    login(admin.id)

    html = client.get("/admin/").get_data(as_text=True)

    assert "Verificaciones pendientes" in html
    assert "/admin/verificaciones" in html


# --- verificacion: el sello en la busqueda publica

def test_el_sello_sale_en_la_busqueda_si_el_servicio_esta_verificado(
    db, client, crear_usuario, crear_post, crear_servicio
):
    autor = crear_usuario(username="autor")
    post = crear_post(autor.id)
    servicio = crear_servicio(post.id, titulo="Instalación de gas")
    servicio.verificado = True
    db.session.commit()

    html = client.get("/servicios/buscar").get_data(as_text=True)

    assert "Instalación de gas" in html
    assert "Verificado" in html


def test_sin_verificar_no_sale_el_sello_en_la_busqueda(
    client, crear_usuario, crear_post, crear_servicio
):
    autor = crear_usuario(username="autor")
    post = crear_post(autor.id)
    crear_servicio(post.id, titulo="Instalación de gas")

    html = client.get("/servicios/buscar").get_data(as_text=True)

    assert "Instalación de gas" in html
    assert "Verificado" not in html


# --- las fotos privadas: quien puede bajar el archivo

@pytest.fixture
def foto_en_disco(app, tmp_path):
    """Escribe un archivo en la carpeta de uploads y devuelve su nombre.

    Escribe en la carpeta PRIVADA, que es de donde leen las dos rutas: si
    escribiera en static/uploads, los tests darian 404 aunque el archivo exista.
    """
    app.config["PRIVATE_UPLOAD_FOLDER"] = str(tmp_path)

    def _crear(nombre="doc.png", contenido=b"contenido-secreto"):
        (tmp_path / nombre).write_bytes(contenido)
        return nombre

    return _crear


@pytest.fixture
def solicitud_con_foto(crear_usuario, crear_post, crear_servicio, crear_solicitud,
                       foto_en_disco):
    """Una solicitud con foto, y las dos personas que pueden verla.

    Devuelve (solicitud, prestador, cliente). Sin login: cada test se loguea
    como quien quiera probar.
    """
    prestador = crear_usuario(username="prestador")
    cliente = crear_usuario(username="cliente")
    post = crear_post(prestador.id)
    servicio = crear_servicio(post.id)
    solicitud = crear_solicitud(servicio.id, cliente.id, foto=foto_en_disco())
    return solicitud, prestador, cliente


@pytest.fixture
def verificacion_con_foto(crear_usuario, crear_post, crear_servicio,
                          crear_verificacion, foto_en_disco):
    """Un pedido de verificacion con foto y el dueño del servicio.

    Devuelve (verificacion, dueño).
    """
    dueño = crear_usuario(username="prestador")
    post = crear_post(dueño.id)
    servicio = crear_servicio(post.id)
    verificacion = crear_verificacion(servicio.id, foto=foto_en_disco())
    return verificacion, dueño


# --- foto de una solicitud de presupuesto: solo las dos partes

def test_el_cliente_baja_la_foto_de_su_solicitud(client, solicitud_con_foto, login):
    solicitud, _prestador, cliente = solicitud_con_foto
    login(cliente.id)

    respuesta = client.get(f"/servicios/solicitudes/{solicitud.id}/foto")

    assert respuesta.status_code == 200
    assert respuesta.data == b"contenido-secreto"


def test_el_prestador_baja_la_foto_de_la_solicitud_que_recibio(
    client, solicitud_con_foto, login
):
    solicitud, prestador, _cliente = solicitud_con_foto
    login(prestador.id)

    assert client.get(f"/servicios/solicitudes/{solicitud.id}/foto").status_code == 200


def test_un_tercero_no_baja_la_foto_de_una_solicitud_ajena(
    client, solicitud_con_foto, crear_usuario, login
):
    solicitud, _prestador, _cliente = solicitud_con_foto
    curioso = crear_usuario(username="curioso")
    login(curioso.id)

    assert client.get(f"/servicios/solicitudes/{solicitud.id}/foto").status_code == 403


def test_un_admin_tampoco_baja_la_foto_de_una_solicitud(
    client, solicitud_con_foto, crear_usuario, login
):
    """La unica privacidad del proyecto donde el admin no entra: una solicitud
    de presupuesto es entre dos personas y punto (ver modelo_solicitud.py)."""
    solicitud, _prestador, _cliente = solicitud_con_foto
    jefa = crear_usuario(username="jefa", rol=Roles.ADMIN)
    login(jefa.id)

    assert client.get(f"/servicios/solicitudes/{solicitud.id}/foto").status_code == 403


def test_un_anonimo_no_baja_la_foto_de_una_solicitud(client, solicitud_con_foto):
    """302 al login y no 403, que es lo que hace login_required en el resto de
    las rutas privadas del blueprint."""
    solicitud, _prestador, _cliente = solicitud_con_foto

    respuesta = client.get(f"/servicios/solicitudes/{solicitud.id}/foto")

    assert respuesta.status_code == 302
    assert "/auth/login" in respuesta.headers["Location"]


def test_la_foto_de_la_solicitud_ya_no_se_pinta_contra_static(
    client, solicitud_con_foto, login
):
    """El control que ata el fix al template: si alguien vuelve a poner
    url_for("static", ...), las rutas nuevas siguen pasando sus tests pero la
    foto queda publica otra vez."""
    solicitud, _prestador, cliente = solicitud_con_foto
    login(cliente.id)

    html = client.get(f"/servicios/solicitudes/{solicitud.id}").get_data(as_text=True)

    assert f"/servicios/solicitudes/{solicitud.id}/foto" in html
    assert "/static/uploads/" not in html


# --- foto de una verificacion: el dueño del servicio y los admins

def test_el_dueño_baja_la_foto_de_su_verificacion(client, verificacion_con_foto, login):
    verificacion, dueño = verificacion_con_foto
    login(dueño.id)

    respuesta = client.get(f"/servicios/verificaciones/{verificacion.id}/foto")

    assert respuesta.status_code == 200
    assert respuesta.data == b"contenido-secreto"


def test_el_admin_baja_la_foto_de_una_verificacion(
    client, verificacion_con_foto, crear_usuario, login
):
    """Aca si entra el admin, al reves que en la solicitud: la verificacion
    existe justamente para que un admin la mire."""
    verificacion, _dueño = verificacion_con_foto
    jefa = crear_usuario(username="jefa", rol=Roles.ADMIN)
    login(jefa.id)

    assert client.get(
        f"/servicios/verificaciones/{verificacion.id}/foto"
    ).status_code == 200


def test_otro_emprendedor_no_baja_la_foto_de_una_verificacion_ajena(
    client, verificacion_con_foto, crear_usuario, login
):
    """Es una matricula con nombre y numero real: no la ve un colega."""
    verificacion, _dueño = verificacion_con_foto
    colega = crear_usuario(username="colega")
    login(colega.id)

    assert client.get(
        f"/servicios/verificaciones/{verificacion.id}/foto"
    ).status_code == 403


def test_un_anonimo_no_baja_la_foto_de_una_verificacion(client, verificacion_con_foto):
    verificacion, _dueño = verificacion_con_foto

    respuesta = client.get(f"/servicios/verificaciones/{verificacion.id}/foto")

    assert respuesta.status_code == 302
    assert "/auth/login" in respuesta.headers["Location"]


def test_la_cola_del_admin_ya_no_linkea_a_static(
    client, verificacion_con_foto, crear_usuario, login
):
    verificacion, _dueño = verificacion_con_foto
    jefa = crear_usuario(username="jefa", rol=Roles.ADMIN)
    login(jefa.id)

    html = client.get("/admin/verificaciones").get_data(as_text=True)

    assert f"/servicios/verificaciones/{verificacion.id}/foto" in html
    assert "/static/uploads/" not in html


# --- archivo que no esta, y nombres que se quieren salir de la carpeta

def test_una_solicitud_sin_foto_da_404(
    client, crear_usuario, crear_post, crear_servicio, crear_solicitud, login
):
    """Sin foto no hay archivo que servir, pero la solicitud existe: 404 y no
    un 500 ni un archivo vacio."""
    prestador = crear_usuario(username="prestador")
    cliente = crear_usuario(username="cliente")
    post = crear_post(prestador.id)
    servicio = crear_servicio(post.id)
    solicitud = crear_solicitud(servicio.id, cliente.id, foto=None)
    login(cliente.id)

    assert client.get(f"/servicios/solicitudes/{solicitud.id}/foto").status_code == 404


def test_una_foto_borrada_del_disco_da_404(
    client, crear_usuario, crear_post, crear_servicio, crear_solicitud, login,
    foto_en_disco
):
    """La fila apunta a un archivo que ya no esta: pasa, y no es un error del
    servidor."""
    foto_en_disco()  # deja la carpeta de uploads apuntando a tmp_path
    prestador = crear_usuario(username="prestador")
    cliente = crear_usuario(username="cliente")
    post = crear_post(prestador.id)
    servicio = crear_servicio(post.id)
    solicitud = crear_solicitud(servicio.id, cliente.id, foto="no-existe.png")
    login(cliente.id)

    assert client.get(f"/servicios/solicitudes/{solicitud.id}/foto").status_code == 404


def test_un_nombre_que_se_sale_de_la_carpeta_no_sirve_el_archivo(
    client, db, tmp_path, app, crear_usuario, crear_post, crear_servicio,
    crear_solicitud, login
):
    """El nombre sale de una columna, no de la URL, asi que el traversal solo
    entra si esa columna quedo envenenada. send_from_directory tiene que
    rechazarlo igual: es la razon de usarlo en vez de send_file.

    El archivo objetivo se crea de verdad, afuera de la carpeta de uploads: sin
    eso el test pasaria por "no existe" en vez de por "no se permite salir".
    """
    privada = tmp_path / "privados"
    privada.mkdir()
    app.config["PRIVATE_UPLOAD_FOLDER"] = str(privada)
    (tmp_path / "secreto.txt").write_bytes(b"esto no se puede servir")

    prestador = crear_usuario(username="prestador")
    cliente = crear_usuario(username="cliente")
    post = crear_post(prestador.id)
    servicio = crear_servicio(post.id)
    solicitud = crear_solicitud(servicio.id, cliente.id, foto="../secreto.txt")
    login(cliente.id)

    respuesta = client.get(f"/servicios/solicitudes/{solicitud.id}/foto")

    assert respuesta.status_code == 404
    assert b"esto no se puede servir" not in respuesta.data


# --- la carpeta privada no se alcanza por /static/

def test_la_carpeta_privada_no_cuelga_de_static():
    """El requisito estructural, antes que cualquier URL concreta.

    Flask sirve su static_folder RECURSIVAMENTE, asi que alcanza con que la
    carpeta privada este adentro para que todo lo que tenga se pueda bajar por
    /static/... sin pasar por ninguna vista. Por eso el chequeo es de rutas y no
    de un GET puntual: cubre cualquier nombre de archivo, no el que se le ocurra
    al test.

    Mira config.Config y no app.config a proposito: en la corrida de tests las
    dos carpetas estan redirigidas a un temporal (ver carpetas_de_subida en
    conftest.py), donde la relacion se cumple sola y el test pasaria sin probar
    nada. Lo que hay que proteger es la config con la que arranca el servidor.
    """
    privada = os.path.abspath(Config.PRIVATE_UPLOAD_FOLDER)
    estatica = os.path.abspath(Config.STATIC_FOLDER)

    assert os.path.commonpath([privada, estatica]) != estatica
    # Y tampoco adentro de UPLOAD_FOLDER, que es la trampa del medio:
    # static/uploads/privado tambien se serviria por /static/uploads/privado/...
    publica = os.path.abspath(Config.UPLOAD_FOLDER)
    assert os.path.commonpath([privada, publica]) != publica


def test_ninguna_ruta_estatica_llega_a_la_carpeta_privada(app, client, tmp_path):
    """El control negativo pedido, por URL y sobre un archivo que existe.

    Se escribe un archivo de verdad en la carpeta privada y se intenta bajarlo
    por todas las formas en que se sirve algo estatico en esta app: la ruta
    /static/ del propio Flask y la de cada blueprint que traiga carpeta estatica
    propia. Ninguna lo tiene que entregar.

    El archivo se crea de verdad a proposito: si no existiera, todas las URLs
    darian 404 igual y el test pasaria sin probar nada.
    """
    privada = tmp_path / "privados"
    privada.mkdir()
    app.config["PRIVATE_UPLOAD_FOLDER"] = str(privada)
    (privada / "matricula.png").write_bytes(b"documento-secreto")

    # Todas las carpetas estaticas registradas: la de la app y la de cada
    # blueprint. Si mañana alguien agrega un blueprint con static_folder propio
    # apuntando a la carpeta privada, este test lo agarra.
    prefijos = [app.static_url_path or "/static"]
    for blueprint in app.blueprints.values():
        if blueprint.static_folder:
            prefijos.append(
                (blueprint.url_prefix or "") + (blueprint.static_url_path or "/static")
            )

    intentos = []
    for prefijo in prefijos:
        intentos += [
            f"{prefijo}/matricula.png",
            f"{prefijo}/privados/matricula.png",
            f"{prefijo}/uploads/privados/matricula.png",
            f"{prefijo}/../privados/matricula.png",
            f"{prefijo}/..%2fprivados%2fmatricula.png",
        ]

    for url in intentos:
        respuesta = client.get(url)
        assert respuesta.status_code != 200, f"{url} entrego el archivo"
        assert b"documento-secreto" not in respuesta.data, f"{url} filtro el contenido"


def test_el_upload_publico_si_se_sigue_bajando_por_static(app, client, tmp_path):
    """El control positivo del anterior: sin esto, "no se puede bajar" podria
    ser que /static/ no sirve nada, y el test de arriba pasaria por el motivo
    equivocado. El resto de los uploads tiene que seguir publico."""
    publica = tmp_path / "publicos"
    publica.mkdir()
    app.config["UPLOAD_FOLDER"] = str(publica)
    (publica / "portada.png").write_bytes(b"foto-de-vitrina")

    # static_folder de la app apunta a static/ del repo, asi que se prueba con
    # un archivo que si vive ahi: el que la app sirve de verdad.
    respuesta = client.get("/static/css/styles.css")

    assert respuesta.status_code == 200
