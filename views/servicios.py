"""Servicios de los emprendimientos: el ABM del prestador.

El ABM vive aca y no en views/blog.py por lo mismo que el de productos y el de
eventos: es su propia entidad, con su propio formulario y su propio panel.

El archivo se llama servicios.py y no services.py a proposito: `services` ya es
el paquete de servicios de dominio del proyecto (services/precios.py,
services/uploads.py), y un modulo de vistas con ese nombre, que ademas importa
de ese paquete, se lee como si fuera lo mismo. El modelo si es models/Service,
que es la convencion de los modelos.

Un servicio pertenece a un emprendimiento (Post), no a un usuario, asi que el
permiso siempre se resuelve mirando el dueño de ese emprendimiento. El chequeo
va en la vista y no solo en el template: esconder un boton no es un permiso,
cualquiera puede mandar el POST a mano.
"""

import os

from flask import (
    Blueprint, abort, current_app, flash, g, redirect, render_template, request, url_for
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload

from db import db, utcnow
from models.post import Post
from models.service import MAX_SERVICIOS_POR_POST, Rubros, Service
from models.service_request import EstadosSolicitud, ServiceRequest
from services.precios import parsear_precio, texto_para_formulario
from services.uploads import borrar_de_disco, save_post_image
from views.auth import login_required

servicios = Blueprint("servicios", __name__, url_prefix="/servicios")


def _upload_dir():
    return os.path.join(current_app.root_path, "static", "uploads")


def _servicio_propio(id):
    """El servicio con ese id si es de un emprendimiento del usuario actual.

    Devuelve (servicio, None) si puede tocarlo, o (None, respuesta) con el
    redirect ya armado si no. Mismo criterio que products._producto_propio:
    flash y vuelta al panel, no un 403 crudo.
    """
    servicio = Service.query.get_or_404(id)
    if servicio.post.author != g.user.id:
        flash("No tenés permiso para modificar este servicio.")
        return None, redirect(url_for("servicios.index"))
    return servicio, None


def _mis_emprendimientos():
    return Post.query.filter_by(author=g.user.id).order_by(Post.title).all()


def _leer_formulario():
    """Los campos del servicio tal como los mando el usuario, ya parseados.

    La validacion es a mano (con flash y una variable `error`) porque asi
    valida todo el proyecto: Flask-WTF esta instalado pero solo se usa para el
    CSRF.
    """
    titulo = (request.form.get("titulo") or "").strip()
    rubro = (request.form.get("rubro") or "").strip()
    descripcion = (request.form.get("descripcion") or "").strip()
    zona = (request.form.get("zona_cobertura") or "").strip()
    precio_texto = (request.form.get("precio_estimado") or "").strip()
    # Un checkbox que no se marca directamente no viaja en el POST.
    disponible = request.form.get("disponible") is not None

    # obligatorio=False: un servicio sin precio es "a presupuestar", que es un
    # caso valido y no un formulario incompleto.
    precio, error_precio = parsear_precio(precio_texto, obligatorio=False)

    error = None
    if not titulo:
        error = "Se requiere un título para el servicio."
    elif rubro not in Rubros.TODOS:
        # El rubro llega de un <select>, pero se valida igual: el POST se puede
        # mandar a mano con cualquier cosa, y un rubro invalido dejaria la fila
        # fuera de la busqueda por rubro sin que nadie se entere.
        error = "Elegí uno de los rubros de la lista."
    elif error_precio:
        error = error_precio

    # Se devuelve el texto crudo del precio y no el Decimal: si estaba mal
    # escrito, el formulario tiene que volver con lo que puso el usuario.
    datos = {
        "titulo": titulo, "rubro": rubro, "descripcion": descripcion,
        "zona_cobertura": zona, "precio_estimado": precio_texto,
        "disponible": disponible,
    }
    return datos, titulo, rubro, descripcion, zona, precio, disponible, error


@servicios.route("/")
@login_required
def index():
    """El panel: todos los servicios de los emprendimientos propios.

    joinedload trae el emprendimiento en la misma consulta, para no disparar un
    SELECT por servicio al mostrar de cual es (el mismo N+1 que el panel de
    productos).
    """
    lista = (
        Service.query
        .join(Post, Post.id == Service.post_id)
        .options(joinedload(Service.post))
        .filter(Post.author == g.user.id)
        .order_by(Post.title, Service.titulo)
        .all()
    )
    return render_template(
        "servicios/index.html",
        servicios=lista,
        posts=_mis_emprendimientos(),
        maximo=MAX_SERVICIOS_POR_POST,
        rubros=Rubros,
    )


@servicios.route("/nuevo", methods=("GET", "POST"))
@login_required
def nuevo():
    """Cargar un servicio en uno de los emprendimientos propios."""
    posts = _mis_emprendimientos()
    if not posts:
        flash("Primero registrá un emprendimiento para poder cargar servicios.")
        return redirect(url_for("blog.my_posts"))

    if request.method == "POST":
        datos, titulo, rubro, descripcion, zona, precio, disponible, error = _leer_formulario()
        post_id = request.form.get("post_id", type=int)
        datos["post_id"] = post_id

        # El emprendimiento no se toma del formulario a ciegas: sin este
        # chequeo cualquiera podria colgar un servicio del emprendimiento de
        # otro mandando un post_id ajeno.
        if error is None and post_id not in {post.id for post in posts}:
            error = "Elegí uno de tus emprendimientos."

        if error is None and _cuantos_tiene(post_id) >= MAX_SERVICIOS_POR_POST:
            error = (
                f"Ese emprendimiento ya tiene {MAX_SERVICIOS_POR_POST} servicios, "
                "que es el máximo. Borrá alguno para cargar uno nuevo."
            )

        if error:
            flash(error)
            return render_template(
                "servicios/form.html", posts=posts, datos=datos,
                servicio=None, rubros=Rubros,
            )

        db.session.add(Service(
            post_id=post_id, titulo=titulo, rubro=rubro,
            descripcion=descripcion or None, zona_cobertura=zona or None,
            precio_estimado=precio, disponible=disponible,
        ))
        db.session.commit()
        flash("Servicio agregado correctamente.")
        return redirect(url_for("servicios.index"))

    datos = {
        "titulo": "", "rubro": Rubros.OTROS, "descripcion": "",
        "zona_cobertura": "", "precio_estimado": "",
        "disponible": True, "post_id": None,
    }
    return render_template(
        "servicios/form.html", posts=posts, datos=datos, servicio=None, rubros=Rubros
    )


@servicios.route("/<int:id>/editar", methods=("GET", "POST"))
@login_required
def editar(id):
    """Editar un servicio propio."""
    servicio, rechazo = _servicio_propio(id)
    if rechazo:
        return rechazo

    posts = _mis_emprendimientos()

    if request.method == "POST":
        datos, titulo, rubro, descripcion, zona, precio, disponible, error = _leer_formulario()
        post_id = request.form.get("post_id", type=int)
        datos["post_id"] = post_id

        if error is None and post_id not in {post.id for post in posts}:
            error = "Elegí uno de tus emprendimientos."

        # El tope solo aplica si el servicio se esta MUDANDO a otro
        # emprendimiento: si se queda donde estaba, ya esta contado.
        if (
            error is None
            and post_id != servicio.post_id
            and _cuantos_tiene(post_id) >= MAX_SERVICIOS_POR_POST
        ):
            error = (
                f"Ese emprendimiento ya tiene {MAX_SERVICIOS_POR_POST} servicios, "
                "que es el máximo."
            )

        if error:
            flash(error)
            return render_template(
                "servicios/form.html", posts=posts, datos=datos,
                servicio=servicio, rubros=Rubros,
            )

        servicio.post_id = post_id
        servicio.titulo = titulo
        servicio.rubro = rubro
        servicio.descripcion = descripcion or None
        servicio.zona_cobertura = zona or None
        servicio.precio_estimado = precio
        servicio.disponible = disponible
        db.session.commit()

        flash("Servicio actualizado correctamente.")
        return redirect(url_for("servicios.index"))

    datos = {
        "titulo": servicio.titulo,
        "rubro": servicio.rubro,
        "descripcion": servicio.descripcion or "",
        "zona_cobertura": servicio.zona_cobertura or "",
        "precio_estimado": texto_para_formulario(servicio.precio_estimado),
        "disponible": servicio.disponible,
        "post_id": servicio.post_id,
    }
    return render_template(
        "servicios/form.html", posts=posts, datos=datos, servicio=servicio, rubros=Rubros
    )


@servicios.route("/<int:id>/eliminar", methods=("POST",))
@login_required
def eliminar(id):
    """Eliminar un servicio propio.

    Solo POST, con la misma razon que blog.delete y products.eliminar: un GET
    no debe tener efectos secundarios (lo puede disparar un prefetch del
    navegador o un crawler).
    """
    servicio, rechazo = _servicio_propio(id)
    if rechazo:
        return rechazo

    db.session.delete(servicio)
    db.session.commit()

    flash("Servicio eliminado correctamente.")
    return redirect(url_for("servicios.index"))


def _cuantos_tiene(post_id):
    """Cuantos servicios tiene ya ese emprendimiento.

    Un COUNT y no len(post.servicios): trae un numero en vez de todas las
    filas solo para contarlas.
    """
    return Service.query.filter_by(post_id=post_id).count()


# ---------------------------------------------------------------- solicitudes

# Como se reconoce el choque contra el UNIQUE de la pendiente unica. Los dos
# motores dicen algo distinto: MySQL nombra la constraint ("Duplicate entry
# '1-2-1' for key 'uq_service_requests_pendiente'") y SQLite no la nombra, lista
# las columnas ("UNIQUE constraint failed: service_requests.service_id, ..."),
# asi que se buscan las dos formas. cupo_pendiente no participa de ninguna otra
# constraint, asi que alcanza para distinguirla.
_CONSTRAINT_PENDIENTE = "uq_service_requests_pendiente"
_COLUMNA_PENDIENTE = "service_requests.cupo_pendiente"


def _es_pendiente_duplicada(error):
    """Si ese IntegrityError es el del UNIQUE de la pendiente unica.

    Se mira antes de dar por hecho de que error se trata: un IntegrityError a
    secas tambien lo levanta, por ejemplo, la FK del servicio si el prestador lo
    borra justo en el medio, y ahi el cliente veria "ya tenes una solicitud
    pendiente", que es mentira, y el error real se perderia sin dejar rastro.
    """
    texto = str(getattr(error, "orig", error))
    return _CONSTRAINT_PENDIENTE in texto or _COLUMNA_PENDIENTE in texto


def _solicitud_visible(id):
    """La solicitud con ese id, si el usuario actual es parte de ella.

    Solo la ven dos personas: el cliente que la hizo y el dueño del
    emprendimiento del que cuelga el servicio. Ni otro emprendedor, ni un
    admin.

    Aca si va abort(403) y no el flash + redirect de _servicio_propio, que es
    el mismo criterio que usa messages.conversation: no es "esto no es tuyo,
    volve a tu panel" sino un limite de privacidad entre dos usuarios
    cualesquiera, y mandarlo a una pagina propia con un cartel amable
    confirmaria igual que la solicitud existe.
    """
    solicitud = ServiceRequest.query.get_or_404(id)
    if g.user.id not in (solicitud.cliente_id, solicitud.servicio.post.author):
        abort(403)
    return solicitud


@servicios.route("/<int:id>/solicitar", methods=("GET", "POST"))
@login_required
def solicitar(id):
    """El cliente pide un presupuesto sobre un servicio."""
    servicio = Service.query.get_or_404(id)

    # El dueño no se pide presupuesto a si mismo.
    if servicio.post.author == g.user.id:
        flash("Es tu propio servicio: las solicitudes te llegan de los clientes.")
        return redirect(url_for("blog.detail", id=servicio.post_id))

    # Un servicio apagado no esta tomando trabajos. El visitante ni siquiera lo
    # ve en el listado, pero el link se puede escribir a mano.
    if not servicio.disponible:
        flash("Ese servicio no está disponible por ahora.")
        return redirect(url_for("blog.detail", id=servicio.post_id))

    pendiente = _solicitud_pendiente_de(servicio.id, g.user.id)
    if pendiente:
        # Sin esto, un doble click en el boton deja dos solicitudes iguales, y
        # nada impide mandar diez. OJO: este chequeo es para mostrar un mensaje
        # claro y llevarlo a la solicitud que ya tiene, no es el que garantiza
        # la regla: entre este SELECT y el INSERT de mas abajo hay una ventana
        # por la que pasan dos requests simultaneos. Lo que de verdad lo impide
        # es el UNIQUE de la base (ver models/service_request.py), y su
        # IntegrityError se maneja abajo.
        flash("Ya tenés una solicitud pendiente para ese servicio.")
        return redirect(url_for("servicios.solicitud", id=pendiente.id))

    if request.method == "POST":
        descripcion = (request.form.get("descripcion") or "").strip()
        zona = (request.form.get("zona") or "").strip()

        error = None
        if not descripcion:
            error = "Contale al prestador qué necesitás."

        foto = None
        if error is None:
            # La foto se guarda al final: si algo de arriba fallaba, no tiene
            # sentido escribir un archivo que despues nadie va a referenciar.
            foto, error = save_post_image(request.files.get("foto"), _upload_dir())

        if error:
            borrar_de_disco(_upload_dir(), [foto])
            flash(error)
            return render_template(
                "servicios/solicitar.html", servicio=servicio,
                datos={"descripcion": descripcion, "zona": zona},
            )

        solicitud = ServiceRequest(
            service_id=servicio.id, cliente_id=g.user.id,
            descripcion=descripcion, zona=zona or None, foto=foto,
            estado=EstadosSolicitud.PENDIENTE,
        )
        db.session.add(solicitud)
        try:
            db.session.commit()
        except IntegrityError as error:
            # La fila no entro, asi que la foto que se acaba de escribir no la
            # referencia nadie: se limpia pase lo que pase con el error.
            db.session.rollback()
            borrar_de_disco(_upload_dir(), [foto])
            if not _es_pendiente_duplicada(error):
                # Cualquier otra violacion de integridad no es este caso y no
                # se disfraza de este caso: sube y se ve como el error que es.
                raise
            # Perdio la carrera: otro request identico llego junto con este y
            # el UNIQUE de la base lo rechazo. Para el usuario es exactamente
            # el mismo caso que atajo el chequeo de arriba, asi que termina
            # igual: en la solicitud que si quedo.
            flash("Ya tenés una solicitud pendiente para ese servicio.")
            pendiente = _solicitud_pendiente_de(servicio.id, g.user.id)
            if pendiente:
                return redirect(url_for("servicios.solicitud", id=pendiente.id))
            # No deberia pasar (si el INSERT choco es porque la otra fila
            # existe), pero si la otra parte se cerro en el medio no se lo deja
            # sin ningun lado al que ir.
            return redirect(url_for("blog.detail", id=servicio.post_id))

        flash("Listo, le mandamos tu pedido. Te va a contestar por acá.")
        return redirect(url_for("servicios.solicitud", id=solicitud.id))

    return render_template(
        "servicios/solicitar.html", servicio=servicio,
        datos={"descripcion": "", "zona": ""},
    )


@servicios.route("/solicitudes")
@login_required
def solicitudes():
    """Las solicitudes del usuario, de los dos lados.

    Una sola pagina con las recibidas (como prestador) y las enviadas (como
    cliente), igual que messages.inbox lista las conversaciones sin importar
    de que lado esta uno: la mitad de los usuarios va a ser las dos cosas, y
    dos paginas separadas obligarian a acordarse de cual mirar.

    Los joinedload evitan el N+1 de ir a buscar el servicio, el emprendimiento
    y el cliente de a una fila por vez al pintar la lista.
    """
    recibidas = (
        ServiceRequest.query
        .join(Service, Service.id == ServiceRequest.service_id)
        .join(Post, Post.id == Service.post_id)
        .options(
            joinedload(ServiceRequest.servicio).joinedload(Service.post),
            joinedload(ServiceRequest.cliente),
        )
        .filter(Post.author == g.user.id)
        .order_by(ServiceRequest.created_at.desc())
        .all()
    )
    enviadas = (
        ServiceRequest.query
        .options(joinedload(ServiceRequest.servicio).joinedload(Service.post))
        .filter(ServiceRequest.cliente_id == g.user.id)
        .order_by(ServiceRequest.created_at.desc())
        .all()
    )
    return render_template(
        "servicios/solicitudes.html",
        recibidas=recibidas,
        enviadas=enviadas,
        estados=EstadosSolicitud,
    )


@servicios.route("/solicitudes/<int:id>")
@login_required
def solicitud(id):
    """El detalle de una solicitud, para las dos partes."""
    solicitud = _solicitud_visible(id)
    return render_template(
        "servicios/solicitud.html",
        solicitud=solicitud,
        es_prestador=(g.user.id == solicitud.servicio.post.author),
        estados=EstadosSolicitud,
    )


@servicios.route("/solicitudes/<int:id>/responder", methods=("POST",))
@login_required
def responder(id):
    """El prestador contesta con un precio y un mensaje.

    Solo el prestador: el cliente es parte de la solicitud y la ve, pero
    responderla es del otro lado. Por eso el chequeo propio y no solo
    _solicitud_visible.
    """
    solicitud = _solicitud_visible(id)
    if g.user.id != solicitud.servicio.post.author:
        flash("La respuesta la escribe quien presta el servicio.")
        return redirect(url_for("servicios.solicitud", id=id))

    if solicitud.estado == EstadosSolicitud.CERRADA:
        flash("Esa solicitud ya está cerrada.")
        return redirect(url_for("servicios.solicitud", id=id))

    mensaje = (request.form.get("respuesta_mensaje") or "").strip()
    # obligatorio=False: se puede contestar sin precio ("pasame una foto",
    # "no llego a esa zona"), pero no sin decir nada.
    precio, error = parsear_precio(
        request.form.get("respuesta_precio") or "", obligatorio=False
    )
    if error is None and not mensaje:
        error = "Escribí una respuesta para el cliente."

    if error:
        flash(error)
        return redirect(url_for("servicios.solicitud", id=id))

    solicitud.respuesta_precio = precio
    solicitud.respuesta_mensaje = mensaje
    solicitud.estado = EstadosSolicitud.RESPONDIDA
    solicitud.responded_at = utcnow()
    db.session.commit()

    flash("Respuesta enviada.")
    return redirect(url_for("servicios.solicitud", id=id))


@servicios.route("/solicitudes/<int:id>/cerrar", methods=("POST",))
@login_required
def cerrar(id):
    """Cierra la solicitud. La puede cerrar cualquiera de las dos partes.

    No es un acuerdo ni una aceptacion: no hay pago ni compromiso de por
    medio, cerrar es archivar. Los dos lados tienen un motivo real para
    hacerlo (el cliente resolvio el problema y no vuelve; el prestador tiene
    que poder limpiar lo que quedo sin contestar), y ninguno de los dos
    motivos es mas legitimo que el otro.

    Solo POST, como todo lo que cambia algo: un GET no debe tener efectos
    secundarios.
    """
    solicitud = _solicitud_visible(id)

    if solicitud.estado == EstadosSolicitud.CERRADA:
        # Ya estaba: no es un error, pero tampoco se vuelve a tocar la fila.
        flash("Esa solicitud ya estaba cerrada.")
    else:
        # No vuelve atras a proposito: reabrir seria otro estado y otra
        # discusion. Si hace falta seguir, se pide de nuevo.
        solicitud.estado = EstadosSolicitud.CERRADA
        db.session.commit()
        flash("Solicitud cerrada.")

    return redirect(url_for("servicios.solicitud", id=id))


def _solicitud_pendiente_de(service_id, cliente_id):
    """La solicitud pendiente de ese cliente sobre ese servicio, si la hay."""
    return ServiceRequest.query.filter_by(
        service_id=service_id,
        cliente_id=cliente_id,
        estado=EstadosSolicitud.PENDIENTE,
    ).first()
