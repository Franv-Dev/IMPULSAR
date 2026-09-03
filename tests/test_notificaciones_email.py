"""Tests de las notificaciones por mail de los tres eventos.

NINGUNO MANDA UN MAIL DE VERDAD, por dos frenos independientes: TestingConfig
deja MAIL_USERNAME y MAIL_PASSWORD en None (y ademas prende MAIL_SUPPRESS_SEND),
y los tests que necesitan que el envio "salga" parchean mail.send por una lista.
Si algun dia los dos frenos se caen a la vez, el que avisa es
test_sin_credenciales_no_se_intenta_conectar.

Lo que se prueba es lo que le importa al negocio, en este orden:

    - que el aviso le llegue a la persona correcta, que en los tres casos es
      "la otra", no la que hizo la accion;
    - que un problema de mail NUNCA se lleve puesto el guardado real;
    - que no se mande dos veces por lo mismo.
"""

from datetime import time, timedelta
from decimal import Decimal

import pytest

from app.perfil.modelo_horario import Horario
from app.servicios.modelo import Service
from app.servicios.modelo_solicitud import EstadosSolicitud, ServiceRequest
from app.turnos.modelo_turno import EstadosTurno, QuienCancela, Turno
from db import db as _db
from models.message import Message
from services import notificaciones_email
from services.eventos import hoy_en_argentina


@pytest.fixture
def buzon(app, monkeypatch):
    """Deja el envio "configurado" y junta los mails en una lista.

    Las credenciales se ponen a mano porque TestingConfig las deja vacias a
    proposito: sin esto _enviar corta antes de armar el mensaje y no habria
    nada que mirar. Son obviamente falsas y no salen de ningun lado.

    mail.send se reemplaza en vez de usar MAIL_SUPPRESS_SEND porque el
    suppress de Flask-Mail igual abre la conexion; aca no se toca la red ni
    para conectar.
    """
    app.config["MAIL_USERNAME"] = "notificaciones@example.com"
    app.config["MAIL_PASSWORD"] = "clave-falsa-de-test"
    app.config["MAIL_DEFAULT_SENDER"] = "notificaciones@example.com"

    enviados = []
    monkeypatch.setattr(
        notificaciones_email.mail, "send", lambda mensaje: enviados.append(mensaje)
    )
    return enviados


@pytest.fixture
def conversacion(db, crear_usuario, crear_post, login):
    """Un emprendimiento con su dueño y un cliente, con el cliente logueado."""

    class Escenario:
        pass

    e = Escenario()
    e.duenio = crear_usuario(username="duenia", email="duenia@example.com")
    e.cliente = crear_usuario(username="clienta", email="clienta@example.com")
    e.post = crear_post(e.duenio.id, title="Panadería del barrio")
    login(e.cliente.id)
    return e


@pytest.fixture
def solicitud_pendiente(db, crear_usuario, crear_post, login):
    """Una solicitud sin contestar, con el prestador logueado para responderla."""

    class Escenario:
        pass

    e = Escenario()
    e.prestador = crear_usuario(username="plomero", email="plomero@example.com")
    e.cliente = crear_usuario(username="vecina", email="vecina@example.com")
    post = crear_post(e.prestador.id, title="Plomería 24hs")
    e.servicio = Service(post_id=post.id, titulo="Destapaciones", rubro="plomeria")
    db.session.add(e.servicio)
    db.session.commit()
    e.solicitud = ServiceRequest(
        service_id=e.servicio.id, cliente_id=e.cliente.id,
        descripcion="Se me tapó la cocina",
    )
    db.session.add(e.solicitud)
    db.session.commit()
    login(e.prestador.id)
    return e


@pytest.fixture
def turno_activo(db, crear_usuario, crear_post, login):
    """Un turno reservado, con las dos partes a mano para loguear la que toque."""

    class Escenario:
        pass

    e = Escenario()
    e.vendedor = crear_usuario(username="peluquera", email="peluquera@example.com")
    e.cliente = crear_usuario(username="clienta", email="clienta@example.com")
    post = crear_post(e.vendedor.id, title="Peluquería")
    db.session.add(Horario(user_id=e.vendedor.id, dia_semana=0,
                           abre=time(9, 0), cierra=time(11, 0), cerrado=False))
    e.servicio = Service(
        post_id=post.id, titulo="Corte", rubro="otros",
        turnos_habilitados=True, duracion_turno_minutos=30,
    )
    db.session.add(e.servicio)
    db.session.commit()
    # Una fecha futura fija en dia habil, por lo mismo que test_turnos: un
    # turno pasado no se puede cancelar y el test empezaria a fallar solo.
    hoy = hoy_en_argentina()
    e.fecha = hoy + timedelta(days=(7 - hoy.weekday()) % 7 or 7)
    e.turno = Turno(
        service_id=e.servicio.id, cliente_id=e.cliente.id, fecha=e.fecha,
        hora_inicio=time(9, 30), hora_fin=time(10, 0),
    )
    db.session.add(e.turno)
    db.session.commit()
    return e


# ------------------------------------------------- el freno de configuracion

def test_sin_credenciales_no_se_intenta_conectar(app, conversacion, monkeypatch):
    """El caso de todos los dias: una copia local, o los tests, sin .env de mail.

    Lo que importa es que mail.send NO se llame: llamarlo sin credenciales
    seria un socket a smtp.gmail.com colgado del request, con su timeout.
    """
    llamadas = []
    monkeypatch.setattr(
        notificaciones_email.mail, "send", lambda m: llamadas.append(m)
    )

    with app.test_request_context():
        mensaje = Message(
            post_id=conversacion.post.id, client_id=conversacion.cliente.id,
            sender_id=conversacion.cliente.id, body="Hola",
        )
        _db.session.add(mensaje)
        _db.session.commit()

        enviado = notificaciones_email.notificar_mensaje_nuevo(mensaje)

    assert enviado is False
    assert llamadas == []


def test_un_destinatario_sin_mail_no_rompe_ni_manda(app, db, buzon, conversacion):
    """El mail es NOT NULL en users, pero la funcion igual no da por sentado
    que haya algo del otro lado: una fila vieja o una relacion que no resuelve
    tienen que terminar en "no se mando", no en una excepcion."""
    conversacion.duenio.email = ""
    db.session.commit()

    with app.test_request_context():
        mensaje = Message(
            post_id=conversacion.post.id, client_id=conversacion.cliente.id,
            sender_id=conversacion.cliente.id, body="Hola",
        )
        db.session.add(mensaje)
        db.session.commit()

        assert notificaciones_email.notificar_mensaje_nuevo(mensaje) is False

    assert buzon == []


# -------------------------------------------------------------- mensaje nuevo

def test_el_mensaje_del_cliente_le_llega_al_dueño(client, buzon, conversacion):
    respuesta = client.post(
        f"/mensajes/{conversacion.post.id}/{conversacion.cliente.id}",
        data={"body": "¿Hacen tortas por encargo?"},
    )

    assert respuesta.status_code == 302
    assert len(buzon) == 1
    mail = buzon[0]
    assert mail.recipients == ["duenia@example.com"]
    assert "Panadería del barrio" in mail.subject
    # El link directo a la conversacion es la mitad del valor del aviso: sin
    # el, el que lo recibe tiene que ir a buscar el hilo a mano.
    assert (
        f"/mensajes/{conversacion.post.id}/{conversacion.cliente.id}"
        in mail.body
    )
    assert "clienta" in mail.body


def test_el_mensaje_del_dueño_le_llega_al_cliente(client, buzon, conversacion, login):
    login(conversacion.duenio.id)

    client.post(
        f"/mensajes/{conversacion.post.id}/{conversacion.cliente.id}",
        data={"body": "Sí, con 48hs de aviso."},
    )

    assert len(buzon) == 1
    assert buzon[0].recipients == ["clienta@example.com"]


def test_un_mensaje_vacio_no_manda_ningun_mail(client, buzon, conversacion):
    """No se guarda nada, asi que tampoco hay de que avisar."""
    client.post(
        f"/mensajes/{conversacion.post.id}/{conversacion.cliente.id}",
        data={"body": "   "},
    )

    assert Message.query.count() == 0
    assert buzon == []


def test_si_falla_el_envio_el_mensaje_igual_se_guarda(
    client, buzon, conversacion, monkeypatch
):
    """El punto entero del modulo: SMTP caido no puede costar un mensaje."""

    def explotar(mensaje):
        raise OSError("SMTP caido")

    monkeypatch.setattr(notificaciones_email.mail, "send", explotar)

    respuesta = client.post(
        f"/mensajes/{conversacion.post.id}/{conversacion.cliente.id}",
        data={"body": "¿Hacen tortas por encargo?"},
    )

    assert respuesta.status_code == 302
    guardado = Message.query.one()
    assert guardado.body == "¿Hacen tortas por encargo?"


# ------------------------------------------------------- solicitud respondida

def test_responder_una_solicitud_le_avisa_al_cliente(client, buzon, solicitud_pendiente):
    e = solicitud_pendiente

    client.post(f"/servicios/solicitudes/{e.solicitud.id}/responder", data={
        "respuesta_precio": "25.000,50",
        "respuesta_mensaje": "Puedo ir el martes a la mañana.",
    })

    assert len(buzon) == 1
    mail = buzon[0]
    assert mail.recipients == ["vecina@example.com"]
    assert "Destapaciones" in mail.subject
    # El precio y el mensaje viajan en el cuerpo: son la respuesta, y el mail
    # sirve para leerla sin entrar.
    assert "25.000,50" in mail.body
    assert "Puedo ir el martes a la mañana." in mail.body
    assert f"/servicios/solicitudes/{e.solicitud.id}" in mail.body


def test_corregir_la_respuesta_no_manda_un_segundo_mail(client, buzon, solicitud_pendiente):
    """Un aviso por cambio de estado. El prestador puede retocar la respuesta
    todas las veces que quiera; el cliente ya se entero con el primero."""
    e = solicitud_pendiente
    datos = {"respuesta_precio": "25000", "respuesta_mensaje": "El martes."}

    client.post(f"/servicios/solicitudes/{e.solicitud.id}/responder", data=datos)
    client.post(f"/servicios/solicitudes/{e.solicitud.id}/responder", data={
        "respuesta_precio": "27000", "respuesta_mensaje": "Perdón, 27 mil.",
    })

    assert len(buzon) == 1
    # La correccion si se guarda: lo que no se repite es el mail.
    assert ServiceRequest.query.one().respuesta_precio == Decimal("27000")


def test_una_respuesta_rechazada_no_manda_mail(client, buzon, solicitud_pendiente):
    """Sin mensaje el formulario no pasa, la solicitud sigue pendiente y no hay
    nada que avisar."""
    e = solicitud_pendiente

    client.post(f"/servicios/solicitudes/{e.solicitud.id}/responder", data={
        "respuesta_precio": "25000", "respuesta_mensaje": "  ",
    })

    assert ServiceRequest.query.one().estado == EstadosSolicitud.PENDIENTE
    assert buzon == []


def test_si_falla_el_envio_la_respuesta_igual_se_guarda(
    client, buzon, solicitud_pendiente, monkeypatch
):
    def explotar(mensaje):
        raise OSError("SMTP caido")

    monkeypatch.setattr(notificaciones_email.mail, "send", explotar)
    e = solicitud_pendiente

    client.post(f"/servicios/solicitudes/{e.solicitud.id}/responder", data={
        "respuesta_precio": "25000", "respuesta_mensaje": "El martes.",
    })

    guardada = ServiceRequest.query.one()
    assert guardada.estado == EstadosSolicitud.RESPONDIDA
    assert guardada.respuesta_mensaje == "El martes."


# ----------------------------------------------------------- turno cancelado

def test_si_cancela_el_cliente_le_avisa_al_vendedor(client, buzon, turno_activo, login):
    e = turno_activo
    login(e.cliente.id)

    client.post(f"/turnos/{e.turno.id}/cancelar")

    assert Turno.query.one().estado == EstadosTurno.CANCELADO
    assert len(buzon) == 1
    mail = buzon[0]
    assert mail.recipients == ["peluquera@example.com"]
    assert "Corte" in mail.subject
    # Fecha y hora del turno que se cayo: es lo que necesita para reacomodar
    # el dia sin abrir la app.
    assert "09:30" in mail.body
    assert str(e.fecha.day) in mail.body
    assert "/turnos/agenda" in mail.body


def test_si_cancela_el_vendedor_le_avisa_al_cliente(client, buzon, turno_activo, login):
    e = turno_activo
    login(e.vendedor.id)

    client.post(f"/turnos/{e.turno.id}/cancelar")

    assert len(buzon) == 1
    mail = buzon[0]
    assert mail.recipients == ["clienta@example.com"]
    assert "/turnos/mios" in mail.body


def test_cancelar_un_turno_ya_cancelado_no_vuelve_a_avisar(
    client, buzon, turno_activo, db, login
):
    e = turno_activo
    e.turno.estado = EstadosTurno.CANCELADO
    e.turno.cancelado_por = QuienCancela.CLIENTE
    db.session.commit()
    login(e.cliente.id)

    client.post(f"/turnos/{e.turno.id}/cancelar")

    assert buzon == []


def test_si_falla_el_envio_el_turno_igual_queda_cancelado(
    client, buzon, turno_activo, monkeypatch, login
):
    """Lo que no se puede perder es la liberacion del slot."""

    def explotar(mensaje):
        raise OSError("SMTP caido")

    monkeypatch.setattr(notificaciones_email.mail, "send", explotar)
    e = turno_activo
    login(e.cliente.id)

    client.post(f"/turnos/{e.turno.id}/cancelar")

    cancelado = Turno.query.one()
    assert cancelado.estado == EstadosTurno.CANCELADO
    # cupo_activo en NULL es lo que devuelve el horario a la lista de libres.
    assert cancelado.cupo_activo is None

