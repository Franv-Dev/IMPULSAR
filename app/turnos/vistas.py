"""Las rutas del dominio: HTTP y nada mas.

Lo que queda aca es lo que solo se puede hacer con un request delante: leer el
formulario, elegir el mensaje, redirigir o renderizar. Las decisiones estan en
reglas.py y las consultas en consultas.py, asi que estas funciones se leen como
el guion de la pantalla. Mismo reparto que app/servicios/vistas.py.

El chequeo de permiso va en la vista y no solo en el template: esconder un boton
no es un permiso, cualquiera puede mandar el POST a mano.

DOS FRENOS DISTINTOS A LA DOBLE RESERVA, y conviene no confundirlos:

- el mismo slot del mismo servicio lo garantiza la BASE, con el UNIQUE y la
  columna centinela de modelo_turno.py. La vista chequea antes para dar un
  mensaje lindo, pero si pierde la carrera el que rechaza es el motor;
- el solapamiento entre servicios DISTINTOS del mismo vendedor no lo puede dar
  un UNIQUE, porque un UNIQUE no compara rangos. Lo chequea la aplicacion
  (reglas.hay_solapamiento), y para que ese chequeo valga contra dos requests
  simultaneos la reserva toma antes un candado de fila sobre el vendedor (ver
  consultas.bloquear_agenda_del_vendedor). En MySQL eso lo cierra; en SQLite,
  que es dev y los tests, no hay candado y no hace falta: es monoproceso.
"""

from flask import (
    Blueprint, flash, g, redirect, render_template, request, url_for
)
from sqlalchemy.exc import IntegrityError

from app.servicios import consultas as consultas_servicios
from app.servicios import reglas as reglas_servicios
from app.turnos import consultas, reglas
from app.turnos.modelo_turno import EstadosTurno, QuienCancela, Turno
from services.eventos import formatear_fecha, hoy_en_argentina, parsear_fecha
from services.horarios import ahora_en_argentina, formatear as formatear_hora
from services.horarios import parsear_hora
from views.auth import login_required

turnos = Blueprint(
    "turnos", __name__, url_prefix="/turnos", template_folder="templates"
)


# Los dos se llaman por estos nombres, y no como consultas.X, para que un test
# de concurrencia los pueda parchear: son los unicos puntos donde se puede meter
# la barrera que reproduce la carrera entre el SELECT y el INSERT. Mismo truco
# que servicios.vistas.solicitud_pendiente_de.
slots_disponibles = consultas.slots_disponibles
rangos_ocupados_del_vendedor = consultas.rangos_ocupados_del_vendedor


def _turno_visible(id):
    """El turno con ese id, si el usuario actual es parte de el.

    Devuelve (turno, None) si puede, o (None, respuesta) con el redirect ya
    armado si no. Flash y vuelta a los turnos propios, no un 403 crudo: es el
    patron que pidio la tanda y el mismo de servicios._servicio_propio.
    """
    turno = consultas.turno_por_id_o_404(id)
    if not reglas.es_parte_del_turno(turno, g.user.id):
        flash("Ese turno no es tuyo.")
        return None, redirect(url_for("turnos.mios"))
    return turno, None


def _fecha_pedida():
    """La fecha que mira el calendario: la de ?fecha=, o hoy en Argentina.

    Una fecha mal escrita cae en hoy en vez de cortar con un 400, mismo criterio
    que blog.reglas.categoria_valida con un rubro inexistente: la URL se escribe
    a mano y no tiene por que reventar la pantalla.
    """
    return parsear_fecha(request.args.get("fecha")) or hoy_en_argentina()


@turnos.route("/servicio/<int:id>", methods=("GET", "POST"))
@login_required
def reservar(id):
    """El cliente elige un slot libre y lo reserva."""
    servicio = consultas_servicios.servicio_por_id_o_404(id)

    # El dueño no se saca turno a si mismo. Mismo criterio que
    # servicios.solicitar con las solicitudes de presupuesto.
    if reglas_servicios.es_de(servicio, g.user.id):
        flash("Es tu propio servicio: los turnos te los sacan los clientes.")
        return redirect(url_for("turnos.agenda"))

    # Un servicio apagado no esta tomando trabajos. El visitante ni siquiera lo
    # ve en el listado, pero el link se puede escribir a mano.
    if not servicio.disponible:
        flash("Ese servicio no está tomando trabajos por ahora.")
        return redirect(url_for("blog.detail", id=servicio.post_id))

    if not reglas_servicios.acepta_turnos(servicio):
        flash("Ese servicio no toma turnos. Podés pedirle un presupuesto.")
        return redirect(url_for("servicios.solicitar", id=servicio.id))

    fecha = _fecha_pedida()
    ahora = ahora_en_argentina()

    if request.method == "POST":
        # La fecha del POST viaja en el form y no en la query: el formulario de
        # confirmacion tiene que mandar el mismo dia que se estaba mirando, y no
        # depender de que el redirect haya conservado el ?fecha=.
        fecha = parsear_fecha(request.form.get("fecha")) or fecha
        hora_inicio = parsear_hora(request.form.get("hora_inicio"))
        error = _reservar(servicio, fecha, hora_inicio, ahora)
        if error is None:
            flash(
                f"Listo, reservaste el {formatear_fecha(fecha)} a las "
                f"{formatear_hora(hora_inicio)}."
            )
            return redirect(url_for("turnos.mios"))
        flash(error)
        return redirect(url_for("turnos.reservar", id=servicio.id,
                                fecha=fecha.isoformat()))

    libres = reglas.descartar_pasados(slots_disponibles(servicio, fecha), fecha, ahora)
    return render_template(
        "turnos/reservar.html", servicio=servicio, fecha=fecha, slots=libres,
        hoy=ahora.date(),
    )


def _reservar(servicio, fecha, hora_inicio, ahora):
    """Crea el turno, o devuelve el mensaje de error que corta. None si salio bien.

    Se separa de la vista porque son cuatro rechazos distintos encadenados y
    dentro del cuerpo de la ruta quedaba ilegible; sigue siendo codigo de la
    vista (arma el mensaje para el usuario), no una regla.
    """
    if hora_inicio is None:
        return "Elegí un horario de la lista."

    # El slot pedido tiene que ser uno de los que la pantalla ofrecia. Esto no
    # es cosmetico: sin este chequeo, un POST a mano reserva a las 3 de la
    # mañana, un domingo cerrado, o pisando un turno ajeno, porque la hora
    # vendria del formulario y no del calculo.
    libres = reglas.descartar_pasados(slots_disponibles(servicio, fecha), fecha, ahora)
    elegido = next((par for par in libres if par[0] == hora_inicio), None)
    if elegido is None:
        return "Ese horario ya no está disponible. Elegí otro."

    inicio, fin = elegido

    # El solapamiento cross-service, que el UNIQUE de la base no cubre: el mismo
    # vendedor puede tener "corte" de 30 y "color" de 90, y sin esto los dos se
    # pueden sacar a las 15:00 (ver reglas.hay_solapamiento).
    #
    # El candado va ANTES de la lectura y no despues: es lo que serializa por
    # vendedor a dos clientes que reservan al mismo tiempo. Sin el, los dos leen
    # la agenda vacia y los dos insertan. Con el, el segundo espera aca, y
    # rangos_ocupados_del_vendedor -- que lee con FOR UPDATE, no por casualidad
    # -- le devuelve la agenda ya con el turno del primero.
    consultas.bloquear_agenda_del_vendedor(servicio.post.author)
    ocupados = rangos_ocupados_del_vendedor(servicio.post.author, fecha)
    if reglas.hay_solapamiento(inicio, fin, ocupados):
        return "Ese horario se pisa con otro turno del prestador. Elegí otro."

    turno = Turno(
        service_id=servicio.id, cliente_id=g.user.id, fecha=fecha,
        hora_inicio=inicio, hora_fin=fin, estado=EstadosTurno.ACTIVO,
    )
    try:
        consultas.guardar(turno)
    except IntegrityError as choque:
        consultas.descartar()
        if not reglas.es_slot_duplicado(choque):
            # Cualquier otra violacion de integridad no es este caso y no se
            # disfraza de este caso: sube y se ve como el error que es.
            raise
        # Perdio la carrera: otro cliente agarro el mismo slot entre el calculo
        # de arriba y este INSERT. Para el usuario es el mismo caso que atajo el
        # chequeo de libres, asi que dice lo mismo.
        return "Ese horario lo acaba de tomar otra persona. Elegí otro."
    return None


@turnos.route("/<int:id>/cancelar", methods=("POST",))
@login_required
def cancelar(id):
    """Cancelar un turno propio, del lado que sea.

    Solo POST, con la misma razon que blog.delete y servicios.eliminar: un GET
    no debe tener efectos secundarios (lo puede disparar un prefetch del
    navegador o un crawler).

    El turno no se borra, se marca cancelado: la fila tiene que quedar para que
    la otra parte vea que se cancelo y quien lo hizo. Ademas es lo que libera el
    slot en la base, porque el listener pone cupo_activo en NULL.
    """
    turno, rechazo = _turno_visible(id)
    if rechazo:
        return rechazo

    volver = redirect(url_for(
        "turnos.agenda" if reglas.es_el_vendedor(turno, g.user.id) else "turnos.mios"
    ))

    if not reglas.puede_cancelar(turno, g.user.id):
        # Hoy solo puede ser "ya estaba cancelado": el otro motivo posible
        # (no ser parte) lo ataja _turno_visible antes de llegar aca.
        flash("Ese turno ya estaba cancelado.")
        return volver

    turno.estado = EstadosTurno.CANCELADO
    # De que lado salio se deduce del turno y no se lee del formulario: si
    # viniera del POST, cualquiera podria decir que lo cancelo el otro.
    turno.cancelado_por = reglas.quien_cancela(turno, g.user.id)
    consultas.guardar()

    flash("Turno cancelado.")
    return volver


@turnos.route("/mios")
@login_required
def mios():
    """Los turnos que el usuario reservo como cliente."""
    return render_template(
        "turnos/mios.html",
        turnos=consultas.turnos_de_cliente(g.user.id),
        estados=EstadosTurno,
        quien=QuienCancela,
        ahora=ahora_en_argentina(),
    )


@turnos.route("/agenda")
@login_required
def agenda():
    """Los turnos que le sacaron a los servicios del usuario.

    Pagina aparte de mios() y no las dos mitades en una, al reves que
    servicios.solicitudes: una solicitud de presupuesto es la misma
    conversacion vista de los dos lados, pero la agenda del que atiende y los
    turnos que uno saco se miran en momentos distintos y con cabezas distintas
    (uno es "que tengo que hacer mañana", el otro "adonde tengo que ir").
    """
    return render_template(
        "turnos/agenda.html",
        turnos=consultas.turnos_recibidos_por(g.user.id),
        estados=EstadosTurno,
        quien=QuienCancela,
        ahora=ahora_en_argentina(),
    )
