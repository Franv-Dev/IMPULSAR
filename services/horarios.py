"""Horarios de atencion y calculo de "abierto ahora".

Las columnas DateTime del proyecto guardan UTC (ver db.utcnow), pero un horario
de atencion es hora local del emprendimiento: si se compara la hora guardada
contra utcnow, un negocio que cierra a las 18:00 aparece cerrado desde las
15:00. Por eso todo lo de aca trabaja en hora de Argentina.
"""

from datetime import datetime, time, timedelta, timezone

# Argentina no aplica horario de verano desde 2009, asi que un offset fijo
# alcanza y evita depender de la base de datos de zonas horarias del sistema
# (que en Windows no siempre esta disponible para zoneinfo).
ZONA_ARGENTINA = timezone(timedelta(hours=-3))

# Lunes = 0, igual que datetime.weekday(), para poder indexar sin convertir.
DIAS = (
    (0, "Lunes"),
    (1, "Martes"),
    (2, "Miércoles"),
    (3, "Jueves"),
    (4, "Viernes"),
    (5, "Sábado"),
    (6, "Domingo"),
)

ETIQUETAS_DIAS = dict(DIAS)


def ahora_en_argentina():
    return datetime.now(ZONA_ARGENTINA)


def parsear_hora(texto):
    """Convierte "09:30" en un time, o None si viene vacio o mal escrito."""
    texto = (texto or "").strip()
    if not texto:
        return None
    try:
        return datetime.strptime(texto, "%H:%M").time()
    except ValueError:
        return None


def ventana_actual(ahora=None):
    """(hoy, ayer, momento) en hora argentina, para preguntar "esta abierto".

    Lo usan las dos formas de contestar la misma pregunta: esta_abierto(), que
    la resuelve en Python sobre los horarios de un emprendedor, y el filtro
    "Abierto ahora" del listado, que la resuelve en SQL sobre toda la tabla.
    Las dos necesitan los mismos tres datos y ninguna puede sacarlos de
    datetime.now() a secas: la hora de referencia es la del local, no la del
    servidor ni la del visitante.

    `ayer` viene junto porque un rango que cruza medianoche se atiende de a dos
    dias: a la 01:00 del martes el bar sigue abierto por el horario del lunes.
    """
    ahora = ahora or ahora_en_argentina()
    hoy = ahora.weekday()
    return hoy, (hoy - 1) % 7, ahora.time()


def _abierto_en(horario, momento):
    """Si un horario puntual cubre `momento` (un time), sin cruzar medianoche."""
    return horario.abre <= momento < horario.cierra


def hora_de_cierre(horarios, ahora=None):
    """A que hora cierra la ventana que esta abierta AHORA, o None si esta cerrado.

    `horarios` es la lista de Horario del usuario (uno por dia como mucho).
    Devuelve un `time`, el `cierra` del horario que cubre este momento.

    Es la respuesta larga a la misma pregunta que contesta esta_abierto(): no
    solo si esta abierto, sino hasta cuando. La ficha del emprendimiento la
    necesita para decir "Abierto ahora - cierra 19:00", que es el dato que uno
    realmente busca; con un si/no pelado hay que abrir la tabla de horarios
    para saber si conviene salir.

    Contempla los rangos que cruzan medianoche (un bar de 20:00 a 02:00): a la
    01:00 del martes el negocio esta abierto por el horario del LUNES, no por
    el del martes, y la hora de cierre que devuelve es la de ese rango.
    """
    hoy, ayer, momento = ventana_actual(ahora)

    por_dia = {h.dia_semana: h for h in horarios if not h.cerrado and h.abre and h.cierra}

    horario_hoy = por_dia.get(hoy)
    if horario_hoy:
        if horario_hoy.cierra > horario_hoy.abre:
            if _abierto_en(horario_hoy, momento):
                return horario_hoy.cierra
        # Cruza medianoche: desde que abre hasta las 23:59 sigue siendo hoy.
        elif horario_hoy.cierra < horario_hoy.abre and momento >= horario_hoy.abre:
            return horario_hoy.cierra

    # La otra mitad del rango que cruza medianoche la aporta el dia anterior.
    horario_ayer = por_dia.get(ayer)
    if horario_ayer and horario_ayer.cierra < horario_ayer.abre:
        if momento < horario_ayer.cierra:
            return horario_ayer.cierra

    return None


def esta_abierto(horarios, ahora=None):
    """True si el negocio esta abierto en este momento.

    Se apoya en hora_de_cierre() en vez de repetir su recorrido: son la misma
    pregunta y no pueden contestar distinto. Antes las dos ramas del cruce de
    medianoche vivian aca; moverlas a hora_de_cierre() no cambia ninguna
    respuesta, y saca la posibilidad de que una de las dos se corrija y la otra
    no.
    """
    return hora_de_cierre(horarios, ahora) is not None


MINUTOS_POR_DIA = 24 * 60


def duracion_minutos(abre, cierra):
    """Cuanto dura ese rango, en minutos, contando el cruce de medianoche.

    De 09:00 a 18:00 son 540; de 20:00 a 02:00 son 360, no -1080. La cuenta es
    modulo 24 horas, que es la misma lectura que hace esta_abierto(): cuando
    `cierra` es menor que `abre`, el cierre es del dia siguiente.

    Devuelve None si falta alguna de las dos horas, que es el dia a medio
    cargar y no un rango de cero.

    Ojo con el caso `abre == cierra`: da 0 y no 1440. Es a proposito, porque es
    justo el caso ambiguo que nadie puede leer (¿cerrado siempre o abierto las
    24 horas?) y por eso el formulario lo rechaza; devolver 1440 lo haria pasar
    por el rango mas largo posible en vez de por el mas corto.
    """
    if abre is None or cierra is None:
        return None
    minutos_abre = abre.hour * 60 + abre.minute
    minutos_cierra = cierra.hour * 60 + cierra.minute
    return (minutos_cierra - minutos_abre) % MINUTOS_POR_DIA


def formatear(hora):
    """Un time como "09:30", o cadena vacia si no hay hora cargada."""
    return hora.strftime("%H:%M") if isinstance(hora, time) else ""
