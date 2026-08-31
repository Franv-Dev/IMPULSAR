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


def esta_abierto(horarios, ahora=None):
    """True si el negocio esta abierto en este momento.

    `horarios` es la lista de Horario del usuario (uno por dia como mucho).

    Contempla los rangos que cruzan medianoche (un bar de 20:00 a 02:00): a la
    01:00 del martes el negocio esta abierto por el horario del LUNES, no por
    el del martes. Sin esto, todo lo que cierra pasada la medianoche figuraba
    cerrado justo en sus horas de mas movimiento.
    """
    hoy, ayer, momento = ventana_actual(ahora)

    por_dia = {h.dia_semana: h for h in horarios if not h.cerrado and h.abre and h.cierra}

    horario_hoy = por_dia.get(hoy)
    if horario_hoy:
        if horario_hoy.cierra > horario_hoy.abre:
            if _abierto_en(horario_hoy, momento):
                return True
        # Cruza medianoche: desde que abre hasta las 23:59 sigue siendo hoy.
        elif horario_hoy.cierra < horario_hoy.abre and momento >= horario_hoy.abre:
            return True

    # La otra mitad del rango que cruza medianoche la aporta el dia anterior.
    horario_ayer = por_dia.get(ayer)
    if horario_ayer and horario_ayer.cierra < horario_ayer.abre:
        if momento < horario_ayer.cierra:
            return True

    return False


def formatear(hora):
    """Un time como "09:30", o cadena vacia si no hay hora cargada."""
    return hora.strftime("%H:%M") if isinstance(hora, time) else ""
