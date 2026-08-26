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
    Blueprint, abort, current_app, flash, g, redirect, render_template, request,
    send_from_directory, url_for
)
from sqlalchemy.exc import IntegrityError

from app.servicios import consultas, formulario, reglas
from app.servicios.modelo import MAX_SERVICIOS_POR_POST, Rubros, Service
from app.servicios.modelo_solicitud import EstadosSolicitud, ServiceRequest
from app.servicios.modelo_verificacion import EstadosVerificacion, VerificationRequest
from db import utcnow
from services.precios import texto_para_formulario
from models.user import Roles
from services.uploads import borrar_de_disco, carpeta_privada, save_post_image
from views.auth import login_required

servicios = Blueprint(
    "servicios", __name__, url_prefix="/servicios", template_folder="templates"
)


def _limites_de_turno():
    """El rango valido de duracion, para que el template lo muestre y lo cite.

    Sale de reglas.py y no de numeros escritos en el HTML: el mensaje de error
    del formulario ya los cita desde ahi, y con el rango repetido en la
    plantilla mover el limite dejaria el <input> y el error diciendo cosas
    distintas.
    """
    return {
        "min_duracion_turno": reglas.MIN_DURACION_TURNO_MINUTOS,
        "max_duracion_turno": reglas.MAX_DURACION_TURNO_MINUTOS,
    }


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


def _servir_foto_privada(nombre):
    """Devuelve un archivo de static/uploads, pero solo despues de un chequeo.

    Existe porque las fotos de este dominio son las unicas de todo el proyecto
    que no son publicas: la de una solicitud de presupuesto y la de un pedido
    de verificacion (una matricula con nombre y numero real). El resto de lo
    que vive en static/uploads -- avatares, portadas, fotos de emprendimientos
    y de productos -- se sigue sirviendo directo por Flask, y esta bien: es
    material de vitrina que tiene que verse sin sesion. Por eso son estas dos
    las que se mudaron de carpeta y no todas.

    Quien puede ver que lo decide cada ruta antes de llamar aca; esto es solo
    la entrega del archivo.

    Y no salen de static/uploads sino de carpeta_privada(), que cuelga de la
    raiz del repo y no de static/. Eso es la segunda capa: el chequeo de permiso
    de arriba cubre a quien pide esta URL, y la ubicacion cubre el dia que un
    nginx sirva static/ directo sin preguntarle nada a la app. Flask sirve su
    static_folder recursivamente, asi que una subcarpeta de uploads/ no habria
    alcanzado.

    send_from_directory y no send_file con la ruta armada a mano: send_file
    abriria cualquier cosa que se le pase, y esto recibe un nombre que sale de
    una columna de la base. Si esa columna alguna vez contiene "../../algo"
    (hoy no puede: los nombres se arman con uuid + secure_filename), Flask lo
    rechaza en vez de servir un archivo de afuera de la carpeta.

    Sin foto o con el archivo borrado del disco es un 404 y no un 500: que la
    fila apunte a algo que ya no esta es un caso posible, no un error del
    servidor.
    """
    if not nombre:
        abort(404)
    # send_from_directory ya levanta NotFound si el archivo no existe o si el
    # nombre se sale de la carpeta, asi que no hay que chequearlo por separado.
    return send_from_directory(carpeta_privada(), nombre)


# ------------------------------------------------------------ busqueda publica

@servicios.route("/buscar")
def buscar():
    """La busqueda publica de servicios por rubro y zona.

    Sin @login_required a proposito, y es la unica ruta del blueprint que no lo
    lleva: encontrar "un plomero en Maipu" tiene que poder hacerlo cualquiera,
    incluso sin cuenta. Pedir el presupuesto si necesita estar logueado, pero
    eso ya lo resuelve solicitar().
    """
    rubro, zona, solo_verificados, pagina = formulario.leer_busqueda()
    return render_template(
        "servicios/buscar.html",
        paginacion=consultas.buscar_servicios(
            # Un rubro que no existe no filtra nada, pero se le devuelve igual
            # al template para repintar el <select> con lo que el usuario tenia.
            rubro=rubro if reglas.rubro_valido(rubro) else None,
            zona=zona,
            solo_verificados=solo_verificados,
            pagina=pagina,
            por_pagina=current_app.config["POSTS_POR_PAGINA"],
        ),
        rubros=Rubros.ETIQUETAS,
        rubro_actual=rubro,
        zona_actual=zona,
        solo_verificados_actual=solo_verificados,
    )


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
                servicio=None, rubros=Rubros, **_limites_de_turno(),
            )

        consultas.guardar(Service(post_id=post_id, **valores))
        flash("Servicio agregado correctamente.")
        return redirect(url_for("servicios.index"))

    datos = {
        "titulo": "", "rubro": Rubros.OTROS, "descripcion": "",
        "zona_cobertura": "", "precio_estimado": "",
        "disponible": True, "post_id": None,
        "turnos_habilitados": False, "duracion_turno_minutos": "",
    }
    return render_template(
        "servicios/form.html", posts=posts, datos=datos, servicio=None,
        rubros=Rubros, **_limites_de_turno(),
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
                servicio=servicio, rubros=Rubros, **_limites_de_turno(),
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
        "turnos_habilitados": servicio.turnos_habilitados,
        # Cadena vacia y no None: es lo que el <input> tiene que mostrar cuando
        # el servicio no toma turnos, igual que hace el precio.
        "duracion_turno_minutos": servicio.duracion_turno_minutos or "",
    }
    return render_template(
        "servicios/form.html", posts=posts, datos=datos, servicio=servicio,
        rubros=Rubros, **_limites_de_turno(),
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
            foto, error = save_post_image(request.files.get("foto"), carpeta_privada())

        if error:
            borrar_de_disco(carpeta_privada(), [foto])
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
            borrar_de_disco(carpeta_privada(), [foto])
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

    Los dos lados siguen viniendo enteros en cada carga aunque la pantalla
    muestre uno solo: son las mismas dos consultas de siempre, y traerlas
    juntas es lo que deja poner el numero del otro lado en su solapa sin una
    tercera consulta. El `lado` solo elige cual se pinta.
    """
    recibidas = consultas.solicitudes_recibidas_por(g.user.id)
    enviadas = consultas.solicitudes_enviadas_por(g.user.id)

    # Se normaliza a "recibidas" cualquier cosa que no sea exactamente
    # "enviadas": la solapa viaja en la URL y se escribe a mano.
    lado = "enviadas" if request.args.get("lado") == "enviadas" else "recibidas"

    return render_template(
        "servicios/solicitudes.html",
        recibidas=recibidas,
        enviadas=enviadas,
        lado=lado,
        resumen=reglas.resumen_de_solicitudes(recibidas, utcnow()),
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


@servicios.route("/solicitudes/<int:id>/foto")
@login_required
def foto_de_solicitud(id):
    """La foto que subio el cliente, con el mismo permiso que la pagina.

    Reusa _solicitud_visible, que es exactamente el chequeo de solicitud(): sin
    eso serian dos criterios que hay que acordarse de mover juntos, y el que se
    olvide deja el archivo abierto aunque la pagina siga cerrada. La ven las
    dos partes y nadie mas, ni otro emprendedor ni un admin (ver
    modelo_solicitud.py).
    """
    return _servir_foto_privada(_solicitud_visible(id).foto)


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


# ------------------------------------------------- verificacion de credenciales

# Mismo motivo que solicitud_pendiente_de: se llama por este nombre para que un
# test de concurrencia pueda parchearlo y meter la barrera que reproduce la
# carrera entre el SELECT y el INSERT.
verificacion_pendiente_de = consultas.verificacion_pendiente_de


@servicios.route("/<int:id>/verificar", methods=("GET", "POST"))
@login_required
def verificar(id):
    """El prestador sube su matricula o certificado para que un admin la mire.

    Solo el dueño del servicio, con el mismo _servicio_propio que el resto del
    ABM: si esto lo pudiera pedir cualquiera, un tercero llenaria la cola del
    admin con documentos de servicios que no son suyos.

    Lo unico que se escribe aca es la foto. El estado, el motivo y el
    Service.verificado del otro lado los escribe el admin y nadie mas (ver
    views/admin.py): si el dueño pudiera marcarlo, la verificacion no
    significaria nada.
    """
    servicio, rechazo = _servicio_propio(id)
    if rechazo:
        return rechazo

    pendiente = verificacion_pendiente_de(servicio.id)
    if pendiente:
        # Igual que en solicitar(): esto es para mostrar un mensaje claro, no es
        # lo que garantiza la regla. Entre este SELECT y el INSERT de mas abajo
        # hay una ventana por la que pasan dos requests simultaneos, y lo que
        # de verdad la cierra es el UNIQUE de la base (ver
        # modelo_verificacion.py), cuyo IntegrityError se maneja abajo.
        return render_template(
            "servicios/verificar.html", servicio=servicio, pendiente=pendiente,
            ultima=pendiente, estados=EstadosVerificacion,
        )

    ultima = consultas.ultima_verificacion_de(servicio.id)

    if request.method == "POST":
        foto, error = save_post_image(request.files.get("foto"), carpeta_privada())
        if error is None and not foto:
            # save_post_image devuelve (None, None) cuando no vino ningun
            # archivo, que para el resto del proyecto no es un error. Aca si:
            # sin el documento no hay nada que revisar.
            error = "Subí una foto de tu matrícula o certificado."

        if error:
            borrar_de_disco(carpeta_privada(), [foto])
            flash(error)
            return render_template(
                "servicios/verificar.html", servicio=servicio,
                pendiente=None, ultima=ultima, estados=EstadosVerificacion,
            )

        verificacion = VerificationRequest(service_id=servicio.id, foto=foto)
        try:
            consultas.guardar(verificacion)
        except IntegrityError as choque:
            # La fila no entro, asi que la foto que se acaba de escribir no la
            # referencia nadie: se limpia pase lo que pase con el error.
            consultas.descartar()
            borrar_de_disco(carpeta_privada(), [foto])
            if not reglas.es_verificacion_duplicada(choque):
                # Cualquier otra violacion de integridad no es este caso y no se
                # disfraza de este caso: sube y se ve como el error que es.
                raise
            # Perdio la carrera contra un request identico. Para el usuario es
            # exactamente el mismo caso que atajo el chequeo de arriba.
            flash("Ya tenés un pedido de verificación esperando revisión.")
            return redirect(url_for("servicios.verificar", id=servicio.id))

        flash("Listo, mandamos tu documentación. Un administrador la va a revisar.")
        return redirect(url_for("servicios.verificar", id=servicio.id))

    return render_template(
        "servicios/verificar.html", servicio=servicio, pendiente=None,
        ultima=ultima, estados=EstadosVerificacion,
    )


@servicios.route("/verificaciones/<int:id>/foto")
@login_required
def foto_de_verificacion(id):
    """El documento del pedido, con el mismo permiso que la cola del admin.

    La ruta vive en este blueprint y no en views/admin.py aunque el admin sea
    el que mas la usa: el permiso no es "ser admin" sino "ser admin O el dueño
    del servicio" (ver reglas.puede_ver_la_verificacion), y colgarla de
    @admin_required dejaria al prestador sin poder ver lo que el mismo mando.
    """
    verificacion = consultas.verificacion_por_id_o_404(id)
    if not reglas.puede_ver_la_verificacion(
        verificacion, g.user.id, g.user.rol == Roles.ADMIN
    ):
        # abort(403) y no flash + redirect, mismo criterio que
        # _solicitud_visible: es un limite de privacidad entre personas, no un
        # "esto no es tuyo, volve a tu panel".
        abort(403)
    return _servir_foto_privada(verificacion.foto)
