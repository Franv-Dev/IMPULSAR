"""Todo lo que este dominio le pregunta a la base.

Es la unica capa que arma querys. La aritmetica de horas no esta aca: vive en
reglas.py, que es pura y se prueba sin sesion. Lo que hace este modulo es juntar
las tres cosas que hacen falta para saber que se puede reservar -- el servicio,
el horario de atencion de su dueño y los turnos ya tomados -- y pasarselas.

Va en app/turnos/ y no en services/ (donde estan horarios.py y eventos.py) por
la regla de app/__init__.py: en services/ vive lo que se comparte y no tiene
dueño posible (precios, uploads, slugs). Esto tiene dueño: es el calculo del
dominio de turnos, y de la unica cosa compartida que necesita -- como se lee un
Horario -- ya se ocupa services/horarios.py.
"""

from app.perfil.modelo_horario import Horario
from app.servicios.reglas import acepta_turnos
from app.turnos.modelo_turno import EstadosTurno, Turno
from app.turnos.reglas import cortar_en_slots


def horario_del_dia(user_id, dia_semana):
    """El Horario de atencion de ese usuario para ese dia, si lo cargo.

    dia_semana en el criterio de datetime.weekday() (lunes = 0), que es el mismo
    que guarda la columna y el mismo que usa services.horarios.DIAS. Como el
    UNIQUE de horarios es (user_id, dia_semana), no puede devolver mas de uno.
    """
    return Horario.query.filter_by(user_id=user_id, dia_semana=dia_semana).first()


def horas_tomadas(service_id, fecha):
    """Las horas de inicio ya reservadas de ese servicio ese dia, como set.

    Solo los turnos activos: uno cancelado libera el slot, que es exactamente lo
    que hace la columna cupo_activo del lado de la base.

    Devuelve las horas y no las filas enteras porque es lo unico que se compara,
    y un set porque la comparacion se hace una vez por slot. Traer solo la
    columna ademas evita cargar el objeto entero de cada turno para mirarle un
    campo.
    """
    filas = (
        Turno.query
        .with_entities(Turno.hora_inicio)
        .filter(
            Turno.service_id == service_id,
            Turno.fecha == fecha,
            Turno.estado == EstadosTurno.ACTIVO,
        )
        .all()
    )
    return {fila[0] for fila in filas}


def slots_disponibles(servicio, fecha):
    """Los turnos que un cliente puede reservar en ese servicio y ese dia.

    Devuelve una lista de tuplas (hora_inicio, hora_fin), de la mas temprana a
    la mas tardia, ya sin los slots ocupados. Lista vacia cuando no hay nada que
    ofrecer, que es siempre un resultado valido y nunca un error:

    - el servicio no toma turnos, o los toma pero no tiene duracion cargada
      (ver servicios.reglas.acepta_turnos),
    - el dueño no cargo horario para ese dia de la semana,
    - ese dia esta marcado como cerrado,
    - el horario de ese dia cruza medianoche (excluido en v1, ver
      reglas.cortar_en_slots),
    - la duracion no entra ni una vez en el rango,
    - todos los slots del dia ya estan reservados.

    EL HORARIO SALE DEL DUEÑO DEL EMPRENDIMIENTO, no del servicio: es el mismo
    horario de atencion que ya se muestra en su perfil. Un servicio no tiene
    horario propio y no se le va a agregar uno: el vendedor dice una sola vez
    cuando atiende, y todos sus servicios se cortan de ahi.

    NO FILTRA LO QUE YA PASO. Pedir los slots de un dia de la semana pasada
    devuelve la grilla entera del dia, menos lo que estuvo reservado. Esta bien
    para lo que hace hoy -- calcular, y nada mas --, pero la pantalla que
    reserve (2b) tiene que cortar por su cuenta el pasado y el "faltan diez
    minutos": eso depende de la hora actual en Argentina, y meterlo aca haria
    que el resultado de la funcion cambie sola entre dos llamadas.
    """
    if not acepta_turnos(servicio):
        return []

    horario = horario_del_dia(servicio.post.author, fecha.weekday())
    if horario is None or horario.cerrado:
        return []

    slots = cortar_en_slots(
        horario.abre, horario.cierra, servicio.duracion_turno_minutos
    )
    if not slots:
        return []

    ocupadas = horas_tomadas(servicio.id, fecha)
    return [(inicio, fin) for inicio, fin in slots if inicio not in ocupadas]
