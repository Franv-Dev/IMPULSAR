"""Las decisiones de negocio del dominio, sin saber que existe HTTP.

Ninguna funcion de aca usa request, flash, redirect ni abort, y ninguna toca la
base: devuelven un bool o un dato. Esa separacion es la que hace que el corte de
slots se pueda probar sin levantar ni un request ni una sesion de SQLAlchemy
(ver tests/test_turnos.py).
"""

from datetime import time

# Como se reconoce el choque contra el UNIQUE de la doble reserva. Los dos
# motores dicen algo distinto: MySQL nombra la constraint ("Duplicate entry
# '3-2026-09-15-15:00:00-1' for key 'uq_turnos_slot_activo'") y SQLite no la
# nombra, lista las columnas ("UNIQUE constraint failed: turnos.service_id,
# turnos.fecha, ..."), asi que se buscan las dos formas. cupo_activo no
# participa de ninguna otra constraint, asi que alcanza para distinguirla.
#
# Son constantes propias y no una funcion generica con la tabla por parametro,
# por lo mismo que en app/servicios/reglas.py: el nombre de la tabla es
# justamente lo que distingue un choque del otro.
_CONSTRAINT_SLOT = "uq_turnos_slot_activo"
_COLUMNA_SLOT = "turnos.cupo_activo"


def es_slot_duplicado(error):
    """Si ese IntegrityError es el del UNIQUE de la doble reserva.

    Analoga a servicios.reglas.es_pendiente_duplicada, y se mira por el mismo
    motivo: un IntegrityError a secas tambien lo levanta, por ejemplo, la FK del
    servicio si el prestador lo borra justo en el medio, y ahi el cliente veria
    "ese horario ya lo tomo otra persona", que es mentira, y el error real se
    perderia sin dejar rastro.
    """
    texto = str(getattr(error, "orig", error))
    return _CONSTRAINT_SLOT in texto or _COLUMNA_SLOT in texto


# ---------------------------------------------------------------- corte de slots

def _en_minutos(hora):
    """Un time como minutos desde la medianoche.

    Toda la aritmetica de horas de este modulo pasa por enteros y no por
    datetime.combine() + timedelta a proposito: combine obliga a inventar una
    fecha, y un rango que se pasa de las 23:59 vuelve como el dia siguiente sin
    avisar, con lo cual una comparacion contra la hora de cierre da al reves.
    Con minutos, pasarse es simplemente un numero mas grande.

    Los segundos se ignoran: un horario de atencion se carga con un
    <input type="time"> en HH:MM y un turno arranca en punto o y media, no a las
    9:00:30.
    """
    return hora.hour * 60 + hora.minute


def _en_hora(minutos):
    """La vuelta de _en_minutos. Solo se llama con valores de un mismo dia."""
    return time(minutos // 60, minutos % 60)


def cruza_medianoche(abre, cierra):
    """Si ese rango termina al dia siguiente (un bar de 20:00 a 02:00).

    Mismo criterio con el que services.horarios.esta_abierto lee un horario
    "dado vuelta": si la hora de cierre no es posterior a la de apertura, el
    rango no se cierra dentro del dia.

    El caso abre == cierra entra aca y tambien devuelve True, o sea que tampoco
    genera slots. Es lo mismo que hace esta_abierto(), que con ese horario
    devuelve siempre False: no hay forma de saber si quiso decir "cero horas" o
    "las veinticuatro", y ninguna de las dos lecturas se puede reservar.
    """
    return cierra <= abre


def cortar_en_slots(abre, cierra, duracion_minutos):
    """Corta un rango de atencion en tramos consecutivos de esa duracion.

    Devuelve una lista de tuplas (hora_inicio, hora_fin), de la mas temprana a
    la mas tardia, sin mirar la base: es el nucleo del calculo y por eso es una
    funcion pura, que se prueba sin levantar ni una sesion.

    Los tramos van pegados uno atras del otro, sin descanso entre medio: en v1
    el vendedor no puede decir "20 minutos de turno y 10 de limpieza". Cuando
    haga falta, sale de una columna mas del Service, no de aca.

    EL SOBRANTE SE DESCARTA. Si la duracion no divide exacto el rango (9:00 a
    13:00 en tramos de 50 minutos deja 40 minutos al final), el ultimo pedazo no
    se ofrece. Es lo unico honesto que se puede hacer: un turno de 50 minutos
    que arranca 12:40 termina 13:30, media hora despues de que el local cerro.
    La alternativa -ofrecerlo igual y que se pase- pone al cliente en la puerta
    de un negocio cerrado, y recortarlo le vende 40 minutos de un servicio que
    dura 50.

    NO EXISTE EL RANGO QUE CRUZA MEDIANOCHE: un horario de 20:00 a 02:00
    devuelve lista vacia (ver cruza_medianoche). Es una exclusion explicita de
    v1 y no un descuido; el dia calendario de un turno de la 01:00 no es el
    mismo que el del horario que lo habilita, y resolver eso toca la fecha que
    se guarda en Turno.fecha, no solo el corte. Lo importante es que no rompe:
    devolver vacio se lee como "ese dia no hay turnos".

    Tampoco genera nada si falta cualquiera de las dos horas, o si la duracion
    no es un numero positivo. Los dos casos deberian ser imposibles (el
    formulario del perfil no deja cargar media hora sola, y
    reglas.duracion_de_turno_valida cuida el rango), pero una fila vieja o
    tocada a mano si los puede tener, y esto tiene que descartarla en vez de
    reventar en la pantalla del cliente.
    """
    if abre is None or cierra is None:
        return []
    if not duracion_minutos or duracion_minutos <= 0:
        return []
    if cruza_medianoche(abre, cierra):
        return []

    inicio = _en_minutos(abre)
    fin = _en_minutos(cierra)

    slots = []
    actual = inicio
    # <= y no <: el ultimo slot puede terminar EXACTAMENTE a la hora de cierre.
    # Un negocio que cierra a las 13:00 atiende el turno de 12:30 a 13:00.
    while actual + duracion_minutos <= fin:
        slots.append((_en_hora(actual), _en_hora(actual + duracion_minutos)))
        actual += duracion_minutos
    return slots


def fin_de_turno(hora_inicio, duracion_minutos):
    """La hora en la que termina un turno que arranca ahi. None si se pasa del dia.

    Es lo que se guarda en Turno.hora_fin al crear la reserva, y por eso vive
    aca y no en la vista: el mismo calculo que corta los slots tiene que ser el
    que congela el rango, o el turno guardado puede no coincidir con el slot que
    el cliente eligio.

    Devuelve None si el turno se pasaria de la medianoche. Sobre un slot salido
    de cortar_en_slots eso no puede pasar (todos terminan como mucho a la hora
    de cierre, que es del mismo dia), asi que un None significa que llego una
    hora que no salio de ahi.
    """
    if hora_inicio is None or not duracion_minutos or duracion_minutos <= 0:
        return None
    fin = _en_minutos(hora_inicio) + duracion_minutos
    if fin >= 24 * 60:
        return None
    return _en_hora(fin)
