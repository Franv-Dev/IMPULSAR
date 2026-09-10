"""Todo lo que el panel le pregunta a la base.

No consulta entidades propias: junta las de los otros dominios en los dos
numeros que las pantallas del panel necesitan -- lo que espera una respuesta
(pendientes_de) y lo que hay cargado (contadores_de).

Los tres primeros pendientes son los mismos que ya cuenta
/mensajes/notificaciones para el badge de la barra, y por eso salen de aca:
antes vivian escritos a mano adentro de esa vista, y el panel los habria
duplicado. La vista de notificaciones ahora los pide a este modulo, asi que el
criterio de "esto espera una respuesta tuya" se define una sola vez.

Las metricas acumuladas (visitas, favoritos, promedio, seguidores) NO se
recalculan aca: son las de perfil.consultas.estadisticas_de_usuario, que ya las
resolvia para la barra de numeros del perfil propio.
"""

from sqlalchemy import func, or_
from sqlalchemy.orm import joinedload

from app.blog.modelo_post import Post
from app.blog.modelo_imagen import PostImage
from app.blog.modelo_resenia import Review
from app.servicios.modelo import Service
from app.servicios.modelo_solicitud import EstadosSolicitud, ServiceRequest
from app.turnos.modelo_turno import EstadosTurno, Turno
from db import db
from models.event import Event
from models.message import Message
from models.product import Product


def mensajes_sin_leer(user_id):
    """Los mensajes que le mandaron y todavia no abrio.

    Cuenta las dos puntas de la conversacion (es cliente o es dueño del
    emprendimiento) porque el chat es uno solo: lo que espera respuesta espera
    respuesta venga de donde venga.
    """
    return (
        db.session.query(func.count(Message.id))
        .join(Post, Post.id == Message.post_id)
        .filter(
            Message.read_at.is_(None),
            Message.sender_id != user_id,
            or_(Message.client_id == user_id, Post.author == user_id),
        )
        .scalar()
    ) or 0


def resenias_sin_responder(user_id):
    """Las reseñas que le dejaron en sus emprendimientos y no contesto."""
    return (
        db.session.query(func.count(Review.id))
        .join(Post, Post.id == Review.post_id)
        .filter(Review.reply.is_(None), Post.author == user_id)
        .scalar()
    ) or 0


def solicitudes_pendientes(user_id):
    """Los presupuestos que le pidieron y todavia no contesto.

    Las pendientes y no las respondidas: una vez que contesto, la pelota esta
    del otro lado.
    """
    return (
        db.session.query(func.count(ServiceRequest.id))
        .join(Service, Service.id == ServiceRequest.service_id)
        .join(Post, Post.id == Service.post_id)
        .filter(
            ServiceRequest.estado == EstadosSolicitud.PENDIENTE,
            Post.author == user_id,
        )
        .scalar()
    ) or 0


def turnos_de(user_id, fecha):
    """Los turnos activos que le sacaron para ese dia, en orden de reloj.

    Trae las filas y no un COUNT porque la portada muestra el primero con
    nombre y hora ("Taller de torno, 16:00 - Camila Suarez"): un contador
    obligaria a una segunda consulta para decir cual es.

    Los cancelados quedan afuera: un turno cancelado no es algo que tengas que
    atender hoy.
    """
    return (
        Turno.query
        .join(Service, Service.id == Turno.service_id)
        .join(Post, Post.id == Service.post_id)
        .options(joinedload(Turno.servicio), joinedload(Turno.cliente))
        .filter(
            Post.author == user_id,
            Turno.fecha == fecha,
            Turno.estado == EstadosTurno.ACTIVO,
        )
        .order_by(Turno.hora_inicio)
        .all()
    )


def pendientes_de(user_id, hoy):
    """Lo que espera una respuesta suya, para la portada del panel.

    Cuatro consultas y no una: son cuatro tablas sin relacion entre si, y
    cruzarlas en un solo join multiplicaria las filas de cada una por las de
    las otras (el mismo producto cartesiano que evita metricas_de_posts).

    Devuelve los cuatro valores aunque esten en cero. Cual se dibuja lo decide
    la pantalla, que es la que sabe que una fila que dice "0 presupuestos" es
    ruido.
    """
    return {
        "solicitudes": solicitudes_pendientes(user_id),
        "mensajes": mensajes_sin_leer(user_id),
        "turnos_hoy": turnos_de(user_id, hoy),
        "resenias": resenias_sin_responder(user_id),
    }


def contadores_de(user_id, hoy):
    """Los numeros al lado de cada item del menu lateral del panel.

    Van todos juntos en un helper y no consulta por consulta en cada vista
    porque el menu es el mismo en las seis pantallas: si cada una armara los
    suyos, un item nuevo obligaria a tocar las seis.

    Los turnos se cuentan de hoy en adelante y solo los activos: la agenda es
    lo que viene, no el historico.
    """
    emprendimientos = (
        db.session.query(func.count(Post.id))
        .filter(Post.author == user_id)
        .scalar()
    ) or 0

    productos = (
        db.session.query(func.count(Product.id))
        .join(Post, Post.id == Product.post_id)
        .filter(Post.author == user_id)
        .scalar()
    ) or 0

    servicios = (
        db.session.query(func.count(Service.id))
        .join(Post, Post.id == Service.post_id)
        .filter(Post.author == user_id)
        .scalar()
    ) or 0

    turnos = (
        db.session.query(func.count(Turno.id))
        .join(Service, Service.id == Turno.service_id)
        .join(Post, Post.id == Service.post_id)
        .filter(
            Post.author == user_id,
            Turno.fecha >= hoy,
            Turno.estado == EstadosTurno.ACTIVO,
        )
        .scalar()
    ) or 0

    # Los eventos, con el mismo criterio que los turnos: de hoy en adelante.
    # Un contador que incluyera los pasados diria "14" al lado de un item que
    # abre una lista con dos fechas por venir.
    eventos = (
        db.session.query(func.count(Event.id))
        .join(Post, Post.id == Event.post_id)
        .filter(Post.author == user_id, Event.fecha >= hoy)
        .scalar()
    ) or 0

    return {
        "emprendimientos": emprendimientos,
        "productos": productos,
        "servicios": servicios,
        "solicitudes": solicitudes_pendientes(user_id),
        "turnos": turnos,
        "eventos": eventos,
        "resenias": resenias_sin_responder(user_id),
    }


def contenido_de_posts(post_ids, hoy):
    """{post_id: {fotos, ferias}} para la lista de emprendimientos del panel.

    Las otras dos cifras de esa linea (productos y servicios) ya las da
    blog.consultas.metricas_de_posts; estas dos son las que faltaban.

    Las fotos se cuentan sumando la principal (Post.image, una columna) a las
    de post_images (una tabla): son los dos lugares donde vive una foto, por la
    decision de modelo_imagen.py.
    """
    if not post_ids:
        return {}

    extras = dict(
        db.session.query(PostImage.post_id, func.count(PostImage.id))
        .filter(PostImage.post_id.in_(post_ids))
        .group_by(PostImage.post_id)
        .all()
    )

    principales = dict(
        db.session.query(Post.id, Post.image)
        .filter(Post.id.in_(post_ids))
        .all()
    )

    ferias = dict(
        db.session.query(Event.post_id, func.count(Event.id))
        .filter(Event.post_id.in_(post_ids), Event.fecha >= hoy)
        .group_by(Event.post_id)
        .all()
    )

    return {
        post_id: {
            "fotos": extras.get(post_id, 0) + (1 if principales.get(post_id) else 0),
            "ferias": ferias.get(post_id, 0),
        }
        for post_id in post_ids
    }
