"""Chat simple entre un cliente y el dueño de un emprendimiento.

Sin tiempo real: la conversacion se recarga por polling (ver GET .../nuevos)
o simplemente refrescando la pagina. Cada conversacion queda identificada
por (post_id, client_id); el otro lado es siempre post.author.
"""

from flask import Blueprint, abort, flash, g, jsonify, redirect, render_template, request, url_for
from sqlalchemy import func, or_
from sqlalchemy.orm import joinedload

from db import db, utcnow
from models.message import Message
from app.blog.modelo_post import Post
from app.blog.modelo_resenia import Review
from app.servicios.modelo import Service
from app.servicios.modelo_solicitud import EstadosSolicitud, ServiceRequest
from models.user import User
from views.auth import login_required

messages = Blueprint("messages", __name__, url_prefix="/mensajes")


def _get_post_o_404(post_id):
    return Post.query.get_or_404(post_id)


def _puede_ver_conversacion(post, client_id):
    """Solo el cliente de la conversacion o el dueño del emprendimiento."""
    return g.user.id in (client_id, post.author)


@messages.route("/")
@login_required
def inbox():
    """Lista las conversaciones del usuario logueado, como cliente o como dueño."""
    ultimos_ids = (
        db.session.query(func.max(Message.id))
        .join(Post, Post.id == Message.post_id)
        .filter(or_(Message.client_id == g.user.id, Post.author == g.user.id))
        .group_by(Message.post_id, Message.client_id)
    )
    conversaciones = (
        Message.query
        .options(
            joinedload(Message.post).joinedload(Post.author_user),
            joinedload(Message.client),
        )
        .filter(Message.id.in_(ultimos_ids))
        .order_by(Message.created.desc())
        .all()
    )
    return render_template("messages/inbox.html", conversaciones=conversaciones)


@messages.route("/<int:post_id>/<int:client_id>", methods=("GET", "POST"))
@login_required
def conversation(post_id, client_id):
    post = _get_post_o_404(post_id)

    if client_id == post.author:
        abort(404)
    if not _puede_ver_conversacion(post, client_id):
        abort(403)

    if request.method == "POST":
        body = (request.form.get("body") or "").strip()
        if not body:
            flash("Escribí un mensaje antes de enviarlo.")
        else:
            db.session.add(Message(
                post_id=post_id, client_id=client_id, sender_id=g.user.id, body=body,
            ))
            db.session.commit()
        return redirect(url_for("messages.conversation", post_id=post_id, client_id=client_id))

    historial = (
        Message.query
        .filter_by(post_id=post_id, client_id=client_id)
        .order_by(Message.created.asc())
        .all()
    )

    # Al abrir la conversacion se marcan como leidos los mensajes que mando
    # la otra parte: es lo que hace bajar el contador de "sin leer" del navbar.
    (
        Message.query
        .filter(
            Message.post_id == post_id,
            Message.client_id == client_id,
            Message.sender_id != g.user.id,
            Message.read_at.is_(None),
        )
        .update({"read_at": utcnow()}, synchronize_session=False)
    )
    db.session.commit()

    # El otro lado de la conversacion: el dueño si soy el cliente, o el
    # cliente si soy el dueño.
    otra_parte = post.author_user if g.user.id == client_id else User.query.get_or_404(client_id)
    return render_template(
        "messages/conversation.html",
        post=post,
        client_id=client_id,
        historial=historial,
        historial_json=[m.serialize() for m in historial],
        otra_parte=otra_parte,
    )


@messages.route("/<int:post_id>/<int:client_id>/nuevos")
@login_required
def poll(post_id, client_id):
    """Mensajes nuevos desde el id indicado, para el polling del front."""
    post = _get_post_o_404(post_id)
    if not _puede_ver_conversacion(post, client_id):
        abort(403)

    despues_de = request.args.get("after", 0, type=int)
    nuevos = (
        Message.query
        .filter_by(post_id=post_id, client_id=client_id)
        .filter(Message.id > despues_de)
        .order_by(Message.created.asc())
        .all()
    )
    return jsonify({"items": [m.serialize() for m in nuevos]}), 200


@messages.route("/notificaciones")
@login_required
def notifications():
    """Contador para el badge del navbar: mensajes sin leer, reseñas sin
    responder y solicitudes de presupuesto pendientes.

    Reutiliza el mismo mecanismo de polling que ya usa el chat (ver
    static/js/chat.js), solo que este endpoint lo consulta static/js/main.js
    en todas las paginas, no solo dentro de una conversacion.

    Las tres cosas son "algo que espera una respuesta tuya" y por eso van en un
    solo contador. El endpoint queda en el blueprint de mensajes aunque ahora
    cuente cosas de otros dos: moverlo cambiaria la URL que ya consulta el JS
    de todas las paginas, y el nombre del blueprint no vale ese cambio.
    """
    mensajes_sin_leer = (
        db.session.query(func.count(Message.id))
        .join(Post, Post.id == Message.post_id)
        .filter(
            Message.read_at.is_(None),
            Message.sender_id != g.user.id,
            or_(Message.client_id == g.user.id, Post.author == g.user.id),
        )
        .scalar()
    ) or 0

    resenias_sin_responder = (
        db.session.query(func.count(Review.id))
        .join(Post, Post.id == Review.post_id)
        .filter(Review.reply.is_(None), Post.author == g.user.id)
        .scalar()
    ) or 0

    # Las solicitudes que le pidieron al usuario y todavia no contesto. Se
    # cuentan las pendientes y no las respondidas: una vez que contesto, la
    # pelota esta del otro lado.
    solicitudes_pendientes = (
        db.session.query(func.count(ServiceRequest.id))
        .join(Service, Service.id == ServiceRequest.service_id)
        .join(Post, Post.id == Service.post_id)
        .filter(
            ServiceRequest.estado == EstadosSolicitud.PENDIENTE,
            Post.author == g.user.id,
        )
        .scalar()
    ) or 0

    return jsonify({
        "unread_messages": mensajes_sin_leer,
        "unanswered_reviews": resenias_sin_responder,
        "pending_service_requests": solicitudes_pendientes,
        "total": mensajes_sin_leer + resenias_sin_responder + solicitudes_pendientes,
    }), 200
