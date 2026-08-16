"""Las rutas del dominio: HTTP y nada mas.

Lo que queda aca es lo que solo se puede hacer con un request delante: leer el
formulario, elegir el mensaje, redirigir o renderizar. Las decisiones estan en
reglas.py y las consultas en consultas.py, asi que estas funciones se leen como
el guion de la pantalla.

El chequeo de permiso va en la vista y no solo en el template: esconder un boton
no es un permiso, cualquiera puede mandar el POST a mano.

El blueprint se sigue llamando "servicios" y sigue colgando de /servicios: los
url_for de todos los templates lo nombran asi, y renombrarlo es otra tanda.
Trae su propio template_folder, con lo cual las plantillas del dominio viajan
con el codigo del dominio (base.html y los partials siguen saliendo de la
carpeta global de la app).
"""

from flask import (
    Blueprint, abort, flash, g, redirect, render_template, request, url_for
)
from sqlalchemy.exc import IntegrityError

from app.servicios import consultas, formulario, reglas
from app.servicios.modelo import MAX_SERVICIOS_POR_POST, Rubros, Service
from app.servicios.modelo_solicitud import EstadosSolicitud, ServiceRequest
from db import utcnow
from services.precios import texto_para_formulario
from services.uploads import borrar_de_disco, carpeta_uploads, save_post_image
from views.auth import login_required

servicios = Blueprint(
    "servicios", __name__, url_prefix="/servicios", template_folder="templates"
)


def _servicio_propio(id):
    """El servicio con ese id si el usuario actual puede tocarlo.

    Devuelve (servicio, None) si puede, o (None, respuesta) con el redirect ya
    armado si no. Mismo criterio que products: flash y vuelta al panel, no un
    403 crudo.
    """
    servicio = consultas.servicio_por_id_o_404(id)
    if not reglas.es_de(servicio, g.user.id):
        flash("No tenés permiso para modificar este servicio.")
        return None, redirect(url_for("servicios.index"))
    return servicio, None


def _solicitud_visible(id):
    """La solicitud con ese id, si el usuario actual es parte de ella.

    Aca si va abort(403) y no el flash + redirect de _servicio_propio, que es
    el mismo criterio que usa messages.conversation: no es "esto no es tuyo,
    volve a tu panel" sino un limite de privacidad entre dos usuarios
    cualesquiera, y mandarlo a una pagina propia con un cartel amable
    confirmaria igual que la solicitud existe.
    """
    solicitud = consultas.solicitud_por_id_o_404(id)
    if not reglas.es_parte_de_la_solicitud(solicitud, g.user.id):
        abort(403)
    return solicitud


# ----------------------------------------------------------------------- ABM

@servicios.route("/")
@login_required
def index():
    """El panel: todos los servicios de los emprendimientos propios."""
    return render_template(
        "servicios/index.html",
        servicios=consultas.servicios_de(g.user.id),
        posts=consultas.emprendimientos_de(g.user.id),
        maximo=MAX_SERVICIOS_POR_POST,
        rubros=Rubros,
    )


@servicios.route("/nuevo", methods=("GET", "POST"))
@login_required
def nuevo():
    """Cargar un servicio en uno de los emprendimientos propios."""
    posts = consultas.emprendimientos_de(g.user.id)
    if not posts:
        flash("Primero registrá un emprendimiento para poder cargar servicios.")
        return redirect(url_for("blog.my_posts"))

    if request.method == "POST":
        datos, valores, error = formulario.leer_servicio()
        post_id = request.form.get("post_id", type=int)
        datos["post_id"] = post_id

        # El emprendimiento no se toma del formulario a ciegas: sin este
        # chequeo cualquiera podria colgar un servicio del emprendimiento de
        # otro mandando un post_id ajeno.
        if error is None and post_id not in {post.id for post in posts}:
            error = "Elegí uno de tus emprendimientos."

        if error is None and not reglas.hay_lugar(
            consultas.cuantos_servicios_tiene(post_id)
        ):
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

        consultas.guardar(Service(post_id=post_id, **valores))
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

    posts = consultas.emprendimientos_de(g.user.id)

    if request.method == "POST":
        datos, valores, error = formulario.leer_servicio()
        post_id = request.form.get("post_id", type=int)
        datos["post_id"] = post_id

        if error is None and post_id not in {post.id for post in posts}:
            error = "Elegí uno de tus emprendimientos."

        # El tope solo aplica si el servicio se esta MUDANDO a otro
        # emprendimiento: si se queda donde estaba, ya esta contado.
        if (
            error is None
            and post_id != servicio.post_id
            and not reglas.hay_lugar(consultas.cuantos_servicios_tiene(post_id))
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
        for campo, valor in valores.items():
            setattr(servicio, campo, valor)
        consultas.guardar()

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

    consultas.borrar(servicio)
    flash("Servicio eliminado correctamente.")
    return redirect(url_for("servicios.index"))


# ---------------------------------------------------------------- solicitudes

# El chequeo de la pendiente se llama por este nombre, y no como
# consultas.solicitud_pendiente_de, para que se pueda parchear en un test de
# concurrencia: es el unico punto donde se puede meter la barrera que reproduce
# la carrera entre el SELECT y el INSERT (ver tests/test_services.py).
solicitud_pendiente_de = consultas.solicitud_pendiente_de


@servicios.route("/<int:id>/solicitar", methods=("GET", "POST"))
@login_required
def solicitar(id):
    """El cliente pide un presupuesto sobre un servicio."""
    servicio = consultas.servicio_por_id_o_404(id)

    # El dueño no se pide presupuesto a si mismo.
    if reglas.es_de(servicio, g.user.id):
        flash("Es tu propio servicio: las solicitudes te llegan de los clientes.")
        return redirect(url_for("blog.detail", id=servicio.post_id))

    # Un servicio apagado no esta tomando trabajos. El visitante ni siquiera lo
    # ve en el listado, pero el link se puede escribir a mano.
    if not servicio.disponible:
        flash("Ese servicio no está disponible por ahora.")
        return redirect(url_for("blog.detail", id=servicio.post_id))

    pendiente = solicitud_pendiente_de(servicio.id, g.user.id)
    if pendiente:
        # Sin esto, un doble click en el boton deja dos solicitudes iguales, y
        # nada impide mandar diez. OJO: este chequeo es para mostrar un mensaje
        # claro y llevarlo a la solicitud que ya tiene, no es el que garantiza
        # la regla: entre este SELECT y el INSERT de mas abajo hay una ventana
        # por la que pasan dos requests simultaneos. Lo que de verdad lo impide
        # es el UNIQUE de la base (ver modelo_solicitud.py), y su IntegrityError
        # se maneja abajo.
        flash("Ya tenés una solicitud pendiente para ese servicio.")
        return redirect(url_for("servicios.solicitud", id=pendiente.id))

    if request.method == "POST":
        datos, error = formulario.leer_solicitud()

        foto = None
        if error is None:
            # La foto se guarda al final: si algo de arriba fallaba, no tiene
            # sentido escribir un archivo que despues nadie va a referenciar.
            foto, error = save_post_image(request.files.get("foto"), carpeta_uploads())

        if error:
            borrar_de_disco(carpeta_uploads(), [foto])
            flash(error)
            return render_template(
                "servicios/solicitar.html", servicio=servicio, datos=datos,
            )

        solicitud = ServiceRequest(
            service_id=servicio.id, cliente_id=g.user.id,
            descripcion=datos["descripcion"], zona=datos["zona"] or None, foto=foto,
            estado=EstadosSolicitud.PENDIENTE,
        )
        try:
            consultas.guardar(solicitud)
        except IntegrityError as choque:
            # La fila no entro, asi que la foto que se acaba de escribir no la
            # referencia nadie: se limpia pase lo que pase con el error.
            consultas.descartar()
            borrar_de_disco(carpeta_uploads(), [foto])
            if not reglas.es_pendiente_duplicada(choque):
                # Cualquier otra violacion de integridad no es este caso y no
                # se disfraza de este caso: sube y se ve como el error que es.
                raise
            # Perdio la carrera: otro request identico llego junto con este y
            # el UNIQUE de la base lo rechazo. Para el usuario es exactamente
            # el mismo caso que atajo el chequeo de arriba, asi que termina
            # igual: en la solicitud que si quedo.
            flash("Ya tenés una solicitud pendiente para ese servicio.")
            pendiente = solicitud_pendiente_de(servicio.id, g.user.id)
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
    """
    return render_template(
        "servicios/solicitudes.html",
        recibidas=consultas.solicitudes_recibidas_por(g.user.id),
        enviadas=consultas.solicitudes_enviadas_por(g.user.id),
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
        es_prestador=reglas.es_el_prestador(solicitud, g.user.id),
        estados=EstadosSolicitud,
    )


@servicios.route("/solicitudes/<int:id>/responder", methods=("POST",))
@login_required
def responder(id):
    """El prestador contesta con un precio y un mensaje."""
    solicitud = _solicitud_visible(id)
    if not reglas.es_el_prestador(solicitud, g.user.id):
        flash("La respuesta la escribe quien presta el servicio.")
        return redirect(url_for("servicios.solicitud", id=id))

    if reglas.esta_cerrada(solicitud):
        flash("Esa solicitud ya está cerrada.")
        return redirect(url_for("servicios.solicitud", id=id))

    mensaje, precio, error = formulario.leer_respuesta()
    if error:
        flash(error)
        return redirect(url_for("servicios.solicitud", id=id))

    solicitud.respuesta_precio = precio
    solicitud.respuesta_mensaje = mensaje
    solicitud.estado = EstadosSolicitud.RESPONDIDA
    solicitud.responded_at = utcnow()
    consultas.guardar()

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

    if reglas.esta_cerrada(solicitud):
        # Ya estaba: no es un error, pero tampoco se vuelve a tocar la fila.
        flash("Esa solicitud ya estaba cerrada.")
    else:
        # No vuelve atras a proposito: reabrir seria otro estado y otra
        # discusion. Si hace falta seguir, se pide de nuevo.
        solicitud.estado = EstadosSolicitud.CERRADA
        consultas.guardar()
        flash("Solicitud cerrada.")

    return redirect(url_for("servicios.solicitud", id=id))
