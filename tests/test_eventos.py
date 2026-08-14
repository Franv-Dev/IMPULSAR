"""Eventos y ferias de los emprendimientos."""

from datetime import date, time, timedelta

import pytest

from models.event import Event
from services.eventos import hoy_en_argentina, parsear_fecha


@pytest.fixture
def crear_evento(db):
    """Fabrica de eventos. `dias` es a cuantos dias de hoy cae el evento."""

    def _crear(post_id, titulo="Feria de la plaza", dias=7, hora=None, descripcion=None):
        evento = Event(
            post_id=post_id,
            titulo=titulo,
            descripcion=descripcion,
            fecha=hoy_en_argentina() + timedelta(days=dias),
            hora=hora,
        )
        db.session.add(evento)
        db.session.commit()
        return evento

    return _crear


@pytest.fixture
def emprendedor_con_post(crear_usuario, crear_post, login):
    """Un usuario logueado con un emprendimiento propio."""

    def _crear(username="tomy"):
        usuario = crear_usuario(username=username)
        post = crear_post(usuario.id)
        login(usuario.id)
        return usuario, post

    return _crear


# --- fechas

def test_parsear_fecha_acepta_el_formato_del_input_date():
    assert parsear_fecha("2026-09-13") == date(2026, 9, 13)


@pytest.mark.parametrize("texto", ["", None, "13/09/2026", "no es una fecha", "2026-13-40"])
def test_parsear_fecha_devuelve_none_si_no_se_entiende(texto):
    assert parsear_fecha(texto) is None


# --- alta

def test_publicar_un_evento_lo_guarda(client, emprendedor_con_post):
    _usuario, post = emprendedor_con_post()

    respuesta = client.post("/eventos/nuevo", data={
        "post_id": post.id,
        "titulo": "Feria de emprendedores",
        "descripcion": "En la plaza principal",
        "fecha": "2026-09-13",
        "hora": "10:30",
    }, follow_redirects=True)

    assert respuesta.status_code == 200
    evento = Event.query.one()
    assert evento.titulo == "Feria de emprendedores"
    assert evento.fecha == date(2026, 9, 13)
    assert evento.hora == time(10, 30)
    assert evento.post_id == post.id


def test_la_hora_es_opcional(client, emprendedor_con_post):
    _usuario, post = emprendedor_con_post()

    client.post("/eventos/nuevo", data={
        "post_id": post.id, "titulo": "Feria", "fecha": "2026-09-13", "hora": "",
    })

    assert Event.query.one().hora is None


@pytest.mark.parametrize("campos, faltante", [
    ({"titulo": "", "fecha": "2026-09-13"}, "titulo"),
    ({"titulo": "Feria", "fecha": ""}, "fecha vacia"),
    ({"titulo": "Feria", "fecha": "13/09/2026"}, "fecha con formato invalido"),
])
def test_un_evento_incompleto_no_se_guarda(client, emprendedor_con_post, campos, faltante):
    _usuario, post = emprendedor_con_post()

    respuesta = client.post(
        "/eventos/nuevo", data={"post_id": post.id, **campos}, follow_redirects=True
    )

    assert respuesta.status_code == 200
    assert Event.query.count() == 0, f"se guardo un evento con {faltante}"


def test_no_se_puede_colgar_un_evento_del_emprendimiento_de_otro(
    client, crear_usuario, crear_post, login
):
    """El post_id viaja en el formulario: sin validarlo, cualquiera podria
    publicar un evento en el emprendimiento ajeno mandando otro id."""
    ajeno = crear_usuario(username="ajeno")
    post_ajeno = crear_post(ajeno.id, title="Panadería ajena")
    intruso = crear_usuario(username="intruso")
    crear_post(intruso.id, title="Lo mío")
    login(intruso.id)

    client.post("/eventos/nuevo", data={
        "post_id": post_ajeno.id, "titulo": "Feria colada", "fecha": "2026-09-13",
    }, follow_redirects=True)

    assert Event.query.count() == 0


def test_sin_emprendimientos_no_se_puede_publicar(client, crear_usuario, login):
    usuario = crear_usuario()
    login(usuario.id)

    respuesta = client.get("/eventos/nuevo")

    assert respuesta.status_code == 302
    assert "/blog/mis-emprendimientos" in respuesta.headers["Location"]


def test_publicar_requiere_estar_logueado(client):
    respuesta = client.get("/eventos/nuevo")

    assert respuesta.status_code == 302
    assert "/auth/login" in respuesta.headers["Location"]


# --- edicion y borrado

def test_el_dueño_edita_su_evento(client, emprendedor_con_post, crear_evento):
    _usuario, post = emprendedor_con_post()
    evento = crear_evento(post.id, titulo="Nombre viejo")

    client.post(f"/eventos/{evento.id}/editar", data={
        "post_id": post.id, "titulo": "Nombre nuevo", "fecha": "2026-10-01",
    }, follow_redirects=True)

    assert Event.query.get(evento.id).titulo == "Nombre nuevo"


def test_el_dueño_elimina_su_evento(client, emprendedor_con_post, crear_evento):
    _usuario, post = emprendedor_con_post()
    evento = crear_evento(post.id)

    client.post(f"/eventos/{evento.id}/eliminar", follow_redirects=True)

    assert Event.query.count() == 0


def test_un_extraño_no_puede_editar_un_evento_ajeno(
    client, crear_usuario, crear_post, crear_evento, login
):
    dueño = crear_usuario(username="dueño")
    post = crear_post(dueño.id)
    evento = crear_evento(post.id, titulo="Original")
    intruso = crear_usuario(username="intruso")
    login(intruso.id)

    respuesta = client.post(f"/eventos/{evento.id}/editar", data={
        "post_id": post.id, "titulo": "Secuestrado", "fecha": "2026-10-01",
    }, follow_redirects=True)

    assert respuesta.status_code == 200
    assert Event.query.get(evento.id).titulo == "Original"


def test_un_extraño_no_puede_eliminar_un_evento_ajeno(
    client, crear_usuario, crear_post, crear_evento, login
):
    dueño = crear_usuario(username="dueño")
    post = crear_post(dueño.id)
    evento = crear_evento(post.id)
    intruso = crear_usuario(username="intruso")
    login(intruso.id)

    client.post(f"/eventos/{evento.id}/eliminar", follow_redirects=True)

    assert Event.query.count() == 1


def test_eliminar_no_acepta_get(client, emprendedor_con_post, crear_evento):
    """Un GET no debe tener efectos secundarios: lo puede disparar un prefetch."""
    _usuario, post = emprendedor_con_post()
    evento = crear_evento(post.id)

    respuesta = client.get(f"/eventos/{evento.id}/eliminar")

    assert respuesta.status_code == 405
    assert Event.query.count() == 1


# --- cascade

def test_borrar_un_emprendimiento_se_lleva_sus_eventos(
    client, emprendedor_con_post, crear_evento
):
    """En MySQL el default de la FK es RESTRICT: sin el ondelete="CASCADE" esto
    falla con IntegrityError. Los tests usan SQLite, que valida las FK gracias
    al PRAGMA de db.py, asi que el caso queda cubierto de verdad."""
    _usuario, post = emprendedor_con_post()
    crear_evento(post.id)
    crear_evento(post.id, titulo="Otra feria", dias=14)

    respuesta = client.post(f"/blog/delete/{post.id}", follow_redirects=True)

    assert respuesta.status_code == 200
    assert Event.query.count() == 0
