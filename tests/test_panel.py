"""Tests del panel del vendedor: la portada, el menu compartido y el
interruptor de stock del catalogo propio."""

import re
from datetime import time, timedelta
from decimal import Decimal

import pytest

from app.blog.modelo_resenia import Review
from app.servicios.modelo import Service
from app.servicios.modelo_solicitud import EstadosSolicitud, ServiceRequest
from app.turnos.modelo_turno import EstadosTurno, Turno
from models.message import Message
from models.product import Product
from services.eventos import hoy_en_argentina


@pytest.fixture
def crear_producto(db):
    """Fabrica de productos, igual que la de test_products."""

    def _crear(post_id, nombre="Pan de campo", precio="1500.00", disponible=True):
        producto = Product(
            post_id=post_id,
            nombre=nombre,
            precio=Decimal(precio),
            disponible=disponible,
        )
        db.session.add(producto)
        db.session.commit()
        return producto

    return _crear


def _servicio_de(db, post_id, titulo="Service de bici"):
    servicio = Service(
        post_id=post_id,
        titulo=titulo,
        rubro="otros",
        turnos_habilitados=True,
        duracion_turno_minutos=60,
    )
    db.session.add(servicio)
    db.session.commit()
    return servicio


def _turno_de(db, servicio, cliente_id, cuando, hora=time(16, 0)):
    turno = Turno(
        service_id=servicio.id,
        cliente_id=cliente_id,
        fecha=cuando,
        hora_inicio=hora,
        hora_fin=time(hora.hour + 1, 0),
        estado=EstadosTurno.ACTIVO,
    )
    db.session.add(turno)
    db.session.commit()
    return turno


# ------------------------------------------------------------- la portada

def test_el_panel_pide_sesion(client):
    respuesta = client.get("/panel/")

    assert respuesta.status_code == 302
    assert "/auth/login" in respuesta.headers["Location"]


def test_el_panel_no_dibuja_lo_que_esta_en_cero(client, crear_usuario, login):
    """Una fila que dice "0 presupuestos" es ruido: con las cuatro en cero la
    seccion entera no aparece."""
    usuario = crear_usuario(username="tomy")
    login(usuario.id)

    html = client.get("/panel/").get_data(as_text=True)

    assert "Lo que te está esperando" not in html
    assert "Tus números" in html


def test_el_panel_lista_lo_pendiente_con_su_numero(
    client, db, crear_usuario, crear_post, login
):
    vendedor = crear_usuario(username="vendedor")
    cliente = crear_usuario(username="camila")
    post = crear_post(vendedor.id, title="Bicis Mendoza")
    servicio = _servicio_de(db, post.id, titulo="Taller de torno")

    db.session.add(ServiceRequest(
        service_id=servicio.id, cliente_id=cliente.id,
        descripcion="¿Cuánto sale?", estado=EstadosSolicitud.PENDIENTE,
    ))
    db.session.add(Message(
        post_id=post.id, client_id=cliente.id,
        sender_id=cliente.id, body="Hola",
    ))
    db.session.add(Review(post_id=post.id, user_id=cliente.id, rating=4))
    _turno_de(db, servicio, cliente.id, hoy_en_argentina())
    db.session.commit()

    login(vendedor.id)
    html = client.get("/panel/").get_data(as_text=True)

    assert "1 presupuesto sin responder" in html
    assert "1 mensaje sin leer" in html
    assert "1 turno hoy" in html
    assert "1 reseña sin responder" in html
    # El turno se dice con el servicio, la hora y quien lo saco: la fila tiene
    # que servir para saber que es sin entrar a la agenda.
    assert "Taller de torno" in html
    assert "16:00" in html
    assert "camila" in html


def test_el_turno_de_otro_dia_no_es_de_hoy(
    client, db, crear_usuario, crear_post, login
):
    vendedor = crear_usuario(username="vendedor")
    cliente = crear_usuario(username="camila")
    post = crear_post(vendedor.id)
    servicio = _servicio_de(db, post.id)
    _turno_de(db, servicio, cliente.id, hoy_en_argentina() + timedelta(days=2))

    login(vendedor.id)
    html = client.get("/panel/").get_data(as_text=True)

    assert "turno hoy" not in html


def test_el_turno_cancelado_de_hoy_no_cuenta(
    client, db, crear_usuario, crear_post, login
):
    """Un turno cancelado no es algo que tengas que atender hoy."""
    vendedor = crear_usuario(username="vendedor")
    cliente = crear_usuario(username="camila")
    post = crear_post(vendedor.id)
    servicio = _servicio_de(db, post.id)
    turno = _turno_de(db, servicio, cliente.id, hoy_en_argentina())
    turno.estado = EstadosTurno.CANCELADO
    db.session.commit()

    login(vendedor.id)
    html = client.get("/panel/").get_data(as_text=True)

    assert "turno hoy" not in html


def test_el_panel_muestra_las_cinco_metricas(
    client, db, crear_usuario, crear_post, login
):
    vendedor = crear_usuario(username="vendedor")
    cliente = crear_usuario(username="camila")
    post = crear_post(vendedor.id, title="Bicis Mendoza")
    post.views_count = 42
    db.session.add(Review(post_id=post.id, user_id=cliente.id, rating=4, reply="Gracias"))
    db.session.commit()

    login(vendedor.id)
    html = client.get("/panel/").get_data(as_text=True)

    assert "42" in html
    assert "Visitas a tus fichas" in html
    assert "Veces que te guardaron" in html
    assert "Promedio de 1" in html
    assert "Personas que te siguen" in html


def test_el_panel_no_inventa_variaciones_ni_graficos(client, crear_usuario, login):
    """El canvas dibujaba "+18%" y una linea de tendencia: la consulta da el
    total de hoy y no hay historico, asi que no hay con que calcularlos."""
    usuario = crear_usuario(username="tomy")
    login(usuario.id)

    html = client.get("/panel/").get_data(as_text=True)

    assert "%" not in html.split("Tus números")[1].split("Tus emprendimientos")[0]


def test_el_panel_avisa_que_le_falta_a_cada_emprendimiento(
    client, db, crear_usuario, crear_post, crear_producto, login
):
    vendedor = crear_usuario(username="vendedor")
    vacio = crear_post(vendedor.id, title="Conservas del Challao")
    cargado = crear_post(vendedor.id, title="Estudio Verde")
    cargado.image = "foto.png"
    crear_producto(cargado.id)
    db.session.commit()

    login(vendedor.id)
    html = client.get("/panel/").get_data(as_text=True)

    assert "Conservas del Challao" in html
    assert "Sin fotos" in html
    # El que ya tiene foto y producto no arrastra el aviso del otro.
    assert html.count("Sin fotos") == 1
    assert str(vacio.id) in html


def test_el_panel_sin_emprendimientos_invita_a_publicar(
    client, crear_usuario, login
):
    usuario = crear_usuario(username="tomy")
    login(usuario.id)

    html = client.get("/panel/").get_data(as_text=True)

    assert "Todavía no registraste ningún emprendimiento" in html


# ------------------------------------------------------- el menu del panel

MENU = re.compile(
    r'<a href="[^"]*"\s+class="panel-menu__item([^"]*)"\s*([^>]*)>',
)


def test_las_pantallas_del_panel_comparten_el_menu_y_marcan_su_item(
    client, db, crear_usuario, crear_post, login
):
    """Las pantallas del vendedor eran paginas sueltas: lo que las hace una
    seccion es este menu, con SU item marcado en cada una.

    Son ocho items desde la tanda de eventos, que sumo "Eventos y ferias" al
    hacer su pantalla (/eventos/mios). Hasta entonces el item faltaba a
    proposito: no habia adonde llevar."""
    usuario = crear_usuario(username="tomy")
    crear_post(usuario.id)
    login(usuario.id)

    pantallas = (
        "/panel/",
        "/blog/mis-emprendimientos",
        "/productos/mios",
        "/servicios/",
        "/servicios/solicitudes",
        "/turnos/agenda",
        "/eventos/mios",
        "/perfil/tomy/resenias",
    )

    for ruta in pantallas:
        html = client.get(ruta).get_data(as_text=True)

        items = MENU.findall(html)
        assert len(items) == 8, (ruta, len(items))

        activos = [
            atributos for clases, atributos in items
            if "panel-menu__item--activo" in clases
        ]
        assert len(activos) == 1, (ruta, activos)
        assert 'aria-current="page"' in activos[0], (ruta, activos)


def test_el_menu_del_panel_cuenta_lo_que_hay_y_no_lo_que_no(
    client, db, crear_usuario, crear_post, crear_producto, login
):
    """El contador en cero no se dibuja: no dice nada que la pantalla no diga
    mejor, y pinta de pendiente lo que no lo es."""
    usuario = crear_usuario(username="tomy")
    post = crear_post(usuario.id)
    crear_producto(post.id)
    crear_producto(post.id, nombre="Pan dulce")
    login(usuario.id)

    html = client.get("/panel/").get_data(as_text=True)
    menu = html.split('class="panel-menu"')[1].split("</aside>")[0]

    assert '<span class="panel-menu__total">2</span>' in menu
    assert "panel-menu__total--pendiente" not in menu


def test_un_visitante_no_ve_el_menu_del_panel_en_las_resenias(
    client, crear_usuario
):
    """/perfil/<slug>/resenias es publica; el menu es del dueño."""
    dueno = crear_usuario(username="tomy")

    html = client.get(f"/perfil/{dueno.slug}/resenias").get_data(as_text=True)

    assert "panel-menu__item" not in html


# --------------------------------- el catalogo propio y el interruptor

def test_el_catalogo_del_panel_muestra_el_emprendimiento_sin_productos(
    client, db, crear_usuario, crear_post, crear_producto, login
):
    """Antes se recorrian los productos, asi que un emprendimiento vacio no
    existia en la pantalla y no habia desde donde cargarle el primero."""
    usuario = crear_usuario(username="tomy")
    con_productos = crear_post(usuario.id, title="Estudio Verde")
    crear_post(usuario.id, title="Conservas del Challao")
    crear_producto(con_productos.id)
    login(usuario.id)

    html = client.get("/productos/mios").get_data(as_text=True)

    assert "Conservas del Challao" in html
    assert "Todavía no tiene productos cargados" in html
    assert "Cargar el primero" in html


def test_el_catalogo_cuenta_los_que_estan_sin_stock(
    client, crear_usuario, crear_post, crear_producto, login
):
    usuario = crear_usuario(username="tomy")
    post = crear_post(usuario.id)
    crear_producto(post.id, nombre="Pan")
    crear_producto(post.id, nombre="Facturas", disponible=False)
    login(usuario.id)

    html = client.get("/productos/mios").get_data(as_text=True)

    assert "2 productos" in html
    assert "1 sin stock" in html


def test_el_interruptor_apaga_y_prende_un_producto(
    client, db, crear_usuario, crear_post, crear_producto, login
):
    """El unico backend nuevo de la tanda: hasta ahora apagar un producto
    obligaba a abrir el formulario entero y volver a guardar los cinco campos."""
    usuario = crear_usuario(username="tomy")
    post = crear_post(usuario.id)
    producto = crear_producto(post.id, nombre="Pan")
    login(usuario.id)

    client.post(f"/productos/{producto.id}/disponible")
    db.session.refresh(producto)
    assert producto.disponible is False

    client.post(f"/productos/{producto.id}/disponible")
    db.session.refresh(producto)
    assert producto.disponible is True


def test_el_interruptor_no_toca_el_resto_del_producto(
    client, db, crear_usuario, crear_post, crear_producto, login
):
    """Es lo que lo hace valer la pena: cambia una columna y ninguna otra."""
    usuario = crear_usuario(username="tomy")
    post = crear_post(usuario.id)
    producto = crear_producto(post.id, nombre="Pan", precio="1500.00")
    login(usuario.id)

    client.post(f"/productos/{producto.id}/disponible")

    db.session.refresh(producto)
    assert producto.nombre == "Pan"
    assert producto.precio == Decimal("1500.00")


def test_el_interruptor_de_un_producto_ajeno_no_hace_nada(
    client, db, crear_usuario, crear_post, crear_producto, login
):
    """El permiso se resuelve en la vista: esconder el boton no es un permiso."""
    dueno = crear_usuario(username="dueno")
    extrano = crear_usuario(username="extrano")
    post = crear_post(dueno.id)
    producto = crear_producto(post.id)
    login(extrano.id)

    client.post(f"/productos/{producto.id}/disponible")

    db.session.refresh(producto)
    assert producto.disponible is True


def test_el_interruptor_no_se_dispara_con_get(
    client, crear_usuario, crear_post, crear_producto, login
):
    """Con GET lo dispararia cualquier cosa que precargue enlaces."""
    usuario = crear_usuario(username="tomy")
    post = crear_post(usuario.id)
    producto = crear_producto(post.id)
    login(usuario.id)

    assert client.get(f"/productos/{producto.id}/disponible").status_code == 405
