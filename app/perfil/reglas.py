"""Las decisiones de negocio del dominio, sin saber que existe HTTP.

Ninguna funcion de aca usa request, flash, redirect ni abort: devuelven un bool
o un dato, y quien decide como se le cuenta eso al usuario es vistas.py.
"""

from app.servicios.modelo_solicitud import EstadosSolicitud
from app.turnos.modelo_turno import EstadosTurno

# Cuantos eventos ya vencidos se muestran en el desplegable del perfil.
MAX_EVENTOS_PASADOS = 5

# Cuantas filas entran en "Lo que tenes en curso". Es un resumen y no la lista:
# la lista completa vive en /turnos/mios y en /servicios/solicitudes, y el
# bloque termina en un enlace a cada una. Tres alcanza para que se vea que hay
# movimiento sin empujar el resto del perfil fuera de pantalla.
MAX_EN_CURSO = 3

# Cuantas reseñas entran en la pestaña del perfil. Mismo criterio que arriba:
# es la prueba de que a este emprendimiento ya le compraron, no el archivo
# completo, que sigue estando en /perfil/<slug>/resenias paginado.
MAX_RESENIAS_EN_EL_PERFIL = 3


def es_el_dueño(user, visitante):
    """Si quien mira el perfil es el dueño.

    De esto depende que se calculen o no las metricas y la lista de "Sigo a":
    son datos del dueño, con el mismo criterio de privacidad que views_count en
    un post. No se calculan cuando mira otro, asi que no hay forma de que se
    filtren por un error en el template.
    """
    return bool(visitante and visitante.id == user.id)


def turnos_en_curso(turnos, hoy):
    """Los turnos del usuario que todavia no pasaron, del mas proximo primero.

    turnos viene de app.turnos.consultas.turnos_de_cliente, que ordena al reves
    (el mas reciente arriba, que es lo que sirve en /turnos/mios) e incluye los
    cancelados. Aca la pregunta es otra: que tengo por delante. Un turno
    cancelado ya no es nada que hacer, y uno de la semana pasada tampoco.

    El corte es por fecha y no por fecha y hora: un turno de hoy a las 09:00
    sigue apareciendo el resto del dia. Es a proposito, es el dia en el que
    alguien pregunta "¿era hoy?".
    """
    proximos = [
        turno for turno in turnos
        if turno.estado == EstadosTurno.ACTIVO and turno.fecha >= hoy
    ]
    proximos.sort(key=lambda turno: (turno.fecha, turno.hora_inicio))
    return proximos[:MAX_EN_CURSO]


def presupuestos_en_curso(solicitudes):
    """Los presupuestos pedidos que todavia esperan algo.

    Las cerradas quedan afuera: cerrar es archivar (ver EstadosSolicitud), o
    sea justamente decir "esto ya no lo estoy esperando". Las respondidas si
    entran, porque lo que falta ahi es que el cliente las lea.
    """
    abiertas = [
        solicitud for solicitud in solicitudes
        if solicitud.estado != EstadosSolicitud.CERRADA
    ]
    return abiertas[:MAX_EN_CURSO]


def puede_seguir(user, visitante):
    """Nadie se sigue a si mismo.

    No es solo cosmetico: sin esto queda una fila que hace que el usuario se
    vea a si mismo en su propia lista de "Sigo a".
    """
    return bool(visitante) and visitante.id != user.id


# Cuanto tiene que durar, como minimo, un dia de atencion. Es un piso contra el
# tipeo, no una regla de negocio: con el cruce de medianoche un "de 18:00 a
# 09:00" es un rango largo y legitimo, pero un "de 09:00 a 09:05" son cinco
# minutos y es alguien que se equivoco en los minutos. Un cuarto de hora es lo
# mas corto que se puede defender como atencion real (una guardia, un retiro de
# pedidos) sin dejar pasar el typo.
#
# Vive aca y no en la base: la cuenta necesita el modulo de 24 horas del cruce
# de medianoche, que no es lo mismo en MySQL que en SQLite, y ademas es el tipo
# de numero que se va a querer mover sin una migracion.
DURACION_MINIMA_MINUTOS = 15


def horario_del_dia(cerrado, abre, cierra):
    """Como queda guardado un dia del panel de horarios: (cerrado, abre, cierra).

    Un dia sin horas cargadas se guarda como cerrado: deja la fila completa en
    vez de a medias, y el indicador de "abierto ahora" la lee igual.
    """
    cerrado = cerrado or not (abre and cierra)
    return cerrado, None if cerrado else abre, None if cerrado else cierra
