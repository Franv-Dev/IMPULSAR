"""Avisos por mail de las tres cosas que hoy solo se ven volviendo a la app.

EL PROBLEMA QUE RESUELVE. La app ya sabe perfectamente que le falta contestar a
cada uno: es el contador del navbar (ver views/messages.py:notifications). Lo
que no hace es salir a buscar a la persona. Un vendedor que no abre la pagina
en dos dias se entera tarde de una solicitud, y esa es una venta perdida. Los
tres eventos que se notifican son justamente los que tienen a alguien
esperando del otro lado:

    - un mensaje nuevo en una conversacion,
    - una solicitud de presupuesto que el vendedor contesto,
    - un turno que cancelo cualquiera de las dos partes.

QUIEN RECIBE CADA UNO SE DECIDE ACA Y NO EN LA VISTA. Las tres funciones
publicas reciben la fila (el Message, la ServiceRequest, el Turno) y sacan el
destinatario de ella, con el mismo criterio que ya usan las vistas para decidir
que mostrarle a cada lado. La vista solo dice "esto paso"; a quien le importa
es de este modulo. Por eso hay una funcion por evento y no un enviar_mail()
generico: el asunto, el texto y el destinatario de cada aviso son parte del
aviso, no del transporte.

NUNCA ROMPE EL FLUJO REAL. Todo lo que sale de aca esta envuelto en un try
amplio y devuelve True/False: si el SMTP esta caido, si Gmail rechaza la clave
o si el destinatario no tiene mail cargado, el mensaje/la respuesta/la
cancelacion YA se guardaron y no se pierden. Queda el log y nada mas. Es a
proposito que el except sea Exception pelado: la lista de lo que puede tirar
smtplib (timeouts, DNS, TLS, auth, direcciones invalidas) es larga y no hay
ninguna que valga romperle el POST al usuario.

SIN CREDENCIALES NO SE INTENTA CONECTAR. Una copia local recien clonada, y la
corrida de tests, no tienen MAIL_USERNAME ni MAIL_PASSWORD: en ese caso se
loguea "no configurado" y se corta antes de abrir el socket, que si no serian
varios segundos de timeout colgados de un request.

Los mails son texto plano. Un aviso de dos lineas con un link no necesita HTML,
y el texto plano entra en cualquier cliente y no depende de que el lector
cargue imagenes.
"""

import logging

from flask import current_app, url_for
from flask_mail import Mail
from flask_mail import Message as MailMessage

from app.turnos.modelo_turno import QuienCancela
from services.eventos import formatear_fecha
from services.horarios import formatear as formatear_hora
from services.precios import formatear as formatear_precio

logger = logging.getLogger(__name__)

# La extension. Se crea vacia aca y la enlaza create_app(), igual que db,
# migrate, jwt y csrf en main.py. Vive en este modulo y no alla porque el unico
# que la usa es este archivo: main.py solo tiene que acordarse del init_app.
mail = Mail()

# Como firma la plataforma sus avisos.
FIRMA = "\n\n--\nIMPULSAR"


def _hay_credenciales():
    """True si la app tiene con que autenticarse contra el SMTP."""
    config = current_app.config
    return bool(config.get("MAIL_USERNAME") and config.get("MAIL_PASSWORD"))


def _enviar(destinatario, asunto, cuerpo):
    """Manda un mail y devuelve si salio. No lanza nunca.

    `destinatario` es un User y no una direccion: los tres llamadores tienen la
    fila del usuario a mano y ninguno tiene por que saber que el mail sale de
    User.email. Puede venir en None (una relacion que ya no resuelve), y eso no
    es un error que valga una excepcion: es un aviso que no se manda.
    """
    direccion = (getattr(destinatario, "email", None) or "").strip()
    if not direccion:
        logger.warning("Notificacion sin destinatario valido: %s", asunto)
        return False

    if not _hay_credenciales():
        # INFO y no WARNING: en desarrollo y en los tests es lo esperado, y un
        # warning por cada mensaje enviado seria ruido puro.
        logger.info("Notificacion no enviada, mail no configurado: %s", asunto)
        return False

    try:
        mail.send(MailMessage(
            subject=asunto,
            recipients=[direccion],
            body=cuerpo + FIRMA,
        ))
    except Exception:
        # Ver "NUNCA ROMPE EL FLUJO REAL" en el docstring del modulo. Se loguea
        # el asunto y no el cuerpo ni la direccion: alcanza para saber que
        # aviso se perdio sin volcar en el log lo que se escribieron dos
        # personas.
        logger.exception("Fallo el envio de la notificacion: %s", asunto)
        return False

    return True


def notificar_mensaje_nuevo(mensaje):
    """Le avisa al que NO escribio que tiene un mensaje esperando.

    El otro lado sale de la misma regla que identifica una conversacion,
    (post_id, client_id): si escribio el cliente, recibe el dueño del
    emprendimiento; si escribio el dueño, recibe el cliente. Ver el docstring
    de models/message.py.
    """
    post = mensaje.post
    if mensaje.sender_id == mensaje.client_id:
        destinatario = post.author_user
    else:
        destinatario = mensaje.client

    enlace = url_for(
        "messages.conversation",
        post_id=mensaje.post_id,
        client_id=mensaje.client_id,
        _external=True,
    )
    quien = mensaje.sender.username if mensaje.sender else "Alguien"

    return _enviar(
        destinatario,
        f"Nuevo mensaje sobre {post.title}",
        f"{quien} te escribio sobre «{post.title}».\n\n"
        f"Podes responderle aca:\n{enlace}",
    )


def notificar_solicitud_respondida(solicitud):
    """Le avisa al cliente que el prestador contesto su pedido de presupuesto.

    UN MAIL POR CAMBIO DE ESTADO, y eso lo decide el que llama: la vista
    notifica solo cuando la solicitud venia en pendiente, asi que corregir la
    respuesta cinco minutos despues no manda un segundo aviso. No hace falta
    nada mas sofisticado (ni una marca de "ya avisado", ni una ventana de
    tiempo) porque una solicitud cruza pendiente -> respondida una sola vez, y
    si el cliente vuelve a preguntar eso es una solicitud nueva, con su fila
    propia y su aviso propio.
    """
    servicio = solicitud.servicio
    enlace = url_for("servicios.solicitud", id=solicitud.id, _external=True)

    cuerpo = [f"Ya te respondieron el presupuesto que pediste por «{servicio.titulo}»."]
    if solicitud.respuesta_precio is not None:
        # El precio se arma con el mismo helper que la pantalla, para que el
        # mail y la pagina no muestren el numero de dos formas distintas.
        cuerpo.append(f"\n\nPresupuesto: {formatear_precio(solicitud.respuesta_precio)}")
    if solicitud.respuesta_mensaje:
        cuerpo.append(f"\n\n{solicitud.respuesta_mensaje}")
    cuerpo.append(f"\n\nVer la solicitud completa:\n{enlace}")

    return _enviar(
        solicitud.cliente,
        f"Respondieron tu solicitud de {servicio.titulo}",
        "".join(cuerpo),
    )


def notificar_turno_cancelado(turno):
    """Le avisa a la OTRA parte que el turno se cayo.

    De que lado salio la cancelacion ya esta en la fila (turno.cancelado_por,
    que escribe la vista con reglas.quien_cancela), asi que el destinatario se
    deduce de ahi: si cancelo el cliente recibe el vendedor, y al reves. No se
    recibe por parametro por lo mismo que la vista no lo lee del formulario.

    El mail dice fecha y hora porque es lo unico que importa del turno que se
    cayo: quien lo lee tiene que poder reacomodar el dia sin abrir la app.
    """
    servicio = turno.servicio
    if turno.cancelado_por == QuienCancela.CLIENTE:
        destinatario = servicio.post.author_user
        quien = "El cliente"
        # Cada lado mira sus turnos en una pagina distinta, y el link tiene que
        # llevar a la que le corresponde al que recibe el mail.
        enlace = url_for("turnos.agenda", _external=True)
    else:
        destinatario = turno.cliente
        quien = "El prestador"
        enlace = url_for("turnos.mios", _external=True)

    cuando = f"{formatear_fecha(turno.fecha)} a las {formatear_hora(turno.hora_inicio)}"

    return _enviar(
        destinatario,
        f"Se cancelo tu turno de {servicio.titulo}",
        f"{quien} cancelo el turno de «{servicio.titulo}» del {cuando}.\n\n"
        f"Ver tus turnos:\n{enlace}",
    )
