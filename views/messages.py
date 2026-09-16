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
from models.product import Product
from models.producto_variante import ProductoVariante
from app.blog.modelo_post import Post
from app.blog import reglas as reglas_blog
from app.panel import consultas as consultas_panel
from models.user import User
from services.notificaciones_email import notificar_mensaje_nuevo
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
    """Lista las conversaciones del usuario logueado, como cliente o como dueño.

    SIN LAS DE LOS EMPRENDIMIENTOS EN BORRADOR, salvo para su dueño. La lista
    muestra el nombre del emprendimiento de cada conversacion, asi que sin este
    filtro el cliente de uno que volvio a borrador lo seguia leyendo aca --y al
    clickearlo se comia el 404 de conversation(), que es lo peor de los dos
    mundos: se entera igual del nombre y encima la pantalla no abre.

    El caso existe: un emprendimiento que estuvo publicado, converso con
    clientes y despues su dueño lo saco de circulacion. Para el DUEÑO la
    conversacion sigue en su lista, que es lo mismo que hace el resto de la app
    con sus borradores.
    """
    ultimos_ids = (
        db.session.query(func.max(Message.id))
        .join(Post, Post.id == Message.post_id)
        .filter(or_(Message.client_id == g.user.id, Post.author == g.user.id))
        .filter(or_(reglas_blog.es_publicado(), Post.author == g.user.id))
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

    # La conversacion nombra el emprendimiento, asi que un borrador se leia
    # desde aca probando ids. 404 y no 403 por lo mismo que la ficha (ver
    # reglas_blog.existe_para), y antes del 403 de mas abajo para que un
    # borrador conteste lo mismo a un tercero que a alguien sin permiso.
    #
    # CONSECUENCIA BUSCADA, no un descuido: si un emprendimiento que ya tenia
    # conversaciones vuelve a borrador, su cliente deja de poder abrir el hilo
    # hasta que se publique de nuevo. Es lo que significa despublicar, y la
    # alternativa --dejar entrar al que ya hablo-- convierte "no existe" en
    # "existe para algunos", que es la regla que esta tanda vino a cerrar.
    if not reglas_blog.existe_para(post, g.user.id):
        abort(404)

    if client_id == post.author:
        abort(404)
    if not _puede_ver_conversacion(post, client_id):
        abort(403)

    if request.method == "POST":
        body = (request.form.get("body") or "").strip()
        if not body:
            flash("Escribí un mensaje antes de enviarlo.")
        else:
            mensaje = Message(
                post_id=post_id, client_id=client_id, sender_id=g.user.id, body=body,
            )
            db.session.add(mensaje)
            db.session.commit()
            # Despues del commit y no antes: si el mail se manda primero y el
            # INSERT despues falla, el otro queda con un aviso de un mensaje
            # que no existe. Al reves no pasa nada malo -- el mensaje ya esta
            # guardado y visible, el mail es el extra. La funcion no lanza
            # aunque el SMTP este caido (ver services/notificaciones_email.py).
            notificar_mensaje_nuevo(mensaje)
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
        borrador=_borrador_por_producto(post),
    )


def _borrador_por_producto(post):
    """El texto con el que arranca el campo cuando se entra desde un producto.

    "Consultar por este producto" (el boton del detalle del catalogo) manda
    aca con ?producto=<id>, y el campo aparece con el nombre del producto ya
    escrito. Es la diferencia entre un chat en blanco -- donde el que pregunta
    tiene que volver a explicar por cual de los catorce frascos escribe -- y
    uno donde el dueño ya sabe de que se trata.

    ES SOLO UN VALOR INICIAL: el usuario lo puede borrar y escribir otra cosa,
    y no viaja ningun dato de mas al POST. Por eso tampoco hace falta validar
    nada mas que la pertenencia.

    SE EXIGE QUE EL PRODUCTO SEA DE ESTE EMPRENDIMIENTO. Sin eso, un id
    cualquiera en la URL escribiria en el campo el nombre de un producto de
    otro, que es una forma barata de poner palabras en la boca del que
    pregunta. Si no coincide (o el id no existe) no se precarga nada, que es
    exactamente lo mismo que entrar por el boton de "Enviar un mensaje".
    """
    producto_id = request.args.get("producto", type=int)
    if producto_id is None:
        return ""

    producto = Product.query.filter_by(id=producto_id, post_id=post.id).first()
    if producto is None:
        return ""

    combinacion = _combinacion_elegida(producto)
    if combinacion:
        return (
            f"Hola, quería consultar por «{producto.nombre}» ({combinacion})."
        )
    return f"Hola, quería consultar por «{producto.nombre}»."


def _combinacion_elegida(producto):
    """La combinacion talle+color que venia en ?variante, si se puede pedir.

    Devuelve la etiqueta ("M / Negro") o "" si no hay ninguna que valga.

    SE REVALIDA ACA, CONTRA LA BASE, y no alcanza con que el selector de la
    ficha solo dibuje las comprables: la URL se escribe a mano, y entre que la
    pagina se dibujo y el click pasaron minutos en los que esa combinacion se
    pudo apagar o quedar en cero. Las tres condiciones son que sea de ESE
    producto (si no, un id cualquiera pondria el talle de otro en la boca del
    que pregunta, igual que con el producto), que este encendida y que tenga
    stock.

    Si algo no da, no se precarga la combinacion pero SI el producto: el que
    pregunta igual quiere preguntar, y dejarlo con el campo en blanco seria
    castigarlo por un stock que cambio.
    """
    variante_id = request.args.get("variante", type=int)
    if variante_id is None:
        return ""

    variante = ProductoVariante.query.filter_by(
        id=variante_id, product_id=producto.id
    ).first()
    if variante is None or not variante.comprable:
        return ""
    return variante.etiqueta


@messages.route("/<int:post_id>/<int:client_id>/nuevos")
@login_required
def poll(post_id, client_id):
    """Mensajes nuevos desde el id indicado, para el polling del front.

    LA MISMA GUARDA QUE conversation(), y no es de mas: esta ruta devuelve el
    contenido de la conversacion en JSON, asi que cortar solo la pantalla dejaba
    la puerta de atras abierta -- y encima abierta al front, que la pide sola
    cada pocos segundos. La encontro el barrido del url_map; una lista fija de
    superficies no la tenia porque nadie piensa en el endpoint de polling.
    """
    post = _get_post_o_404(post_id)
    if not reglas_blog.existe_para(post, g.user.id):
        abort(404)
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

    Los tres conteos viven en app/panel/consultas.py desde la tanda del panel:
    la portada del panel muestra exactamente lo mismo, y escritos a mano en dos
    lados el criterio de "esto espera respuesta" se despegaba al primer cambio.
    """
    mensajes_sin_leer = consultas_panel.mensajes_sin_leer(g.user.id)
    resenias_sin_responder = consultas_panel.resenias_sin_responder(g.user.id)
    solicitudes_pendientes = consultas_panel.solicitudes_pendientes(g.user.id)

    return jsonify({
        "unread_messages": mensajes_sin_leer,
        "unanswered_reviews": resenias_sin_responder,
        "pending_service_requests": solicitudes_pendientes,
        "total": mensajes_sin_leer + resenias_sin_responder + solicitudes_pendientes,
    }), 200
