"""Eventos y ferias: fechas, corte de "ya paso" y consultas compartidas.

La fecha de un evento es hora local de Argentina, no UTC: la misma distincion
que ya hacen los horarios de atencion (ver services/horarios.py), y por eso se
reusa su ZONA_ARGENTINA en vez de definir otro offset.

El corte de "todavia no paso" vive aca y no en cada vista porque lo usan el
perfil y la cartelera: si cada uno lo escribiera por su cuenta, alcanzaria con
que uno de los dos usara utcnow para que un evento aparezca vencido en una
pantalla y vigente en la otra.
"""

from calendar import monthrange
from datetime import date, datetime

from sqlalchemy import extract, func

from models.event import Event, TiposEvento
from app.blog.modelo_post import Post
from services.horarios import ZONA_ARGENTINA


# Los nombres de los meses van escritos y no salen de strftime("%B"): eso
# depende del locale del sistema operativo, que en el servidor puede estar en
# ingles y dejar "13 de September" en pantalla.
MESES = (
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
)


# Lunes = 0, igual que datetime.weekday() y que services.horarios.DIAS.
DIAS_SEMANA = ("lun", "mar", "mie", "jue", "vie", "sab", "dom")


def hoy_en_argentina():
    """La fecha de hoy segun el reloj de Argentina."""
    return datetime.now(ZONA_ARGENTINA).date()


def parsear_fecha(texto):
    """Convierte "2026-09-13" en un date, o None si viene vacio o mal escrito.

    Ese es el formato que manda un <input type="date">. Mismo criterio que
    services.horarios.parsear_hora, que se usa tal cual para la hora.
    """
    texto = (texto or "").strip()
    if not texto:
        return None
    try:
        return datetime.strptime(texto, "%Y-%m-%d").date()
    except ValueError:
        return None


def formatear_fecha(fecha):
    """Un date como "13 de septiembre de 2026". Cadena vacia si no hay fecha."""
    if fecha is None:
        return ""
    return f"{fecha.day} de {MESES[fecha.month - 1]} de {fecha.year}"


def mes_corto(fecha):
    """"sep", para el recuadro de fecha de las tarjetas."""
    return MESES[fecha.month - 1][:3] if fecha else ""


def dia_semana_corto(fecha):
    """"sab", para la linea de arriba del recuadro de fecha.

    Escrito y no strftime("%a") por lo mismo que los meses: depende del locale
    del sistema, que en el servidor puede dejar "Sat 13 sep" en pantalla.
    """
    return DIAS_SEMANA[fecha.weekday()] if fecha else ""


def mes_y_anio(fecha):
    """"agosto 2026", para los encabezados de la cartelera.

    Escrito y no strftime("%B %Y") por lo mismo que MESES: eso depende del
    locale del sistema operativo, que en el servidor puede dejar "August 2026".
    """
    return f"{MESES[fecha.month - 1]} {fecha.year}" if fecha else ""


def agrupar_por_mes(eventos, totales=None):
    """Los eventos en grupos consecutivos de mes, conservando el orden.

    Devuelve [{"nombre": "agosto 2026", "eventos": [...], "total": 13}, ...].
    Se apoya en que la lista YA viene ordenada por fecha (proximos()): agrupa
    cortando cuando cambia el mes, no juntando por clave, asi que dos tramos
    del mismo mes separados en la lista serian dos grupos -- y con la lista
    ordenada eso no puede pasar.

    `total` NO ES len(eventos) cuando se pasan `totales`, y esa es toda la
    razon de que exista el parametro: la cartelera esta paginada, asi que
    `eventos` es un recorte y un mes partido entre dos paginas mostraba dos
    numeros, ninguno de los cuales era el del mes. Los totales de verdad los
    cuenta la base (ver total_por_mes) sobre el mismo filtro y sin el LIMIT.

    Sin `totales` el total es el largo del grupo, que es lo correcto cuando la
    lista que se pasa ya es completa.
    """
    grupos = []
    for evento in eventos:
        clave = (evento.fecha.year, evento.fecha.month)
        if not grupos or grupos[-1]["clave"] != clave:
            grupos.append({
                "clave": clave,
                "nombre": mes_y_anio(evento.fecha),
                "eventos": [],
            })
        grupos[-1]["eventos"].append(evento)

    for grupo in grupos:
        if totales is None:
            grupo["total"] = len(grupo["eventos"])
        else:
            # .get con fallback y no [clave]: si por lo que sea el conteo no
            # trajo ese mes, mostrar lo que hay en la pagina es mejor que
            # reventar la cartelera entera.
            grupo["total"] = totales.get(grupo["clave"], len(grupo["eventos"]))
    return grupos


def total_por_mes(query):
    """Cuantos eventos tiene cada mes en el TOTAL del filtro, no en la pagina.

    Devuelve {(anio, mes): cantidad}. Es un COUNT agrupado contra la base, que
    es la unica forma de saberlo sin traer la cartelera entera a memoria: la
    pantalla muestra una pagina, y el rotulo del mes habla del mes.

    El order_by(None) no es decorativo, y esta medido contra MySQL 8 real: la
    consulta llega ordenada por fecha, hora e id (ver proximos), y esas tres
    columnas no estan en el GROUP BY. Con ONLY_FULL_GROUP_BY -- que MySQL 8
    trae prendido por default -- eso es un OperationalError 1055 ("Expression
    #1 of ORDER BY clause is not in GROUP BY clause"), no una consulta rara que
    anda igual. SQLite lo acepta sin decir nada, asi que sin sacar el orden
    esto seria otro 500 que solo aparece en produccion.
    """
    filas = (
        query.order_by(None)
        .with_entities(
            extract("year", Event.fecha),
            extract("month", Event.fecha),
            func.count(Event.id),
        )
        .group_by(extract("year", Event.fecha), extract("month", Event.fecha))
        .all()
    )
    # int() porque SQLite devuelve los extract como float y las claves tienen
    # que ser comparables con las que arma agrupar_por_mes desde un date.
    return {(int(anio), int(mes)): total for anio, mes, total in filas}


def proximos(query, hoy=None):
    """Eventos que todavia no pasaron, del mas cercano al mas lejano.

    El corte es por dia y no por hora: un evento de hoy sigue anunciandose todo
    el dia aunque su hora ya haya pasado. Para una feria eso es lo correcto (a
    las 11 todavia se puede ir a una que abrio a las 10), y ademas la hora es
    opcional, asi que no siempre hay con que hacer un corte mas fino.

    El id desempata al final y no es decorativo: como la hora es opcional,
    varios eventos del mismo dia sin hora comparten la clave de orden entera, y
    ahi el orden entre ellos lo decide la base, que no garantiza ninguno. Con
    LIMIT/OFFSET (la cartelera esta paginada) eso alcanza para que un evento
    aparezca en dos paginas o en ninguna.
    """
    hoy = hoy or hoy_en_argentina()
    return (
        query.filter(Event.fecha >= hoy)
        .order_by(Event.fecha.asc(), Event.hora.asc(), Event.id.asc())
    )


def pasados(query, hoy=None):
    """Eventos ya vencidos, del mas reciente al mas viejo.

    Desempata por id por lo mismo que proximos(), y en el mismo sentido que el
    resto del orden para que la lista quede coherente.
    """
    hoy = hoy or hoy_en_argentina()
    return (
        query.filter(Event.fecha < hoy)
        .order_by(Event.fecha.desc(), Event.hora.desc(), Event.id.desc())
    )


def parsear_mes(texto):
    """Convierte "2026-08" en (anio, mes), o None si viene vacio o mal escrito.

    Es el formato que manda el calendario del home en ?mes=. Se valida aca y no
    en la vista por lo mismo que parsear_fecha: un mes que no existe tiene que
    dar None y no una excepcion, para que quien llame decida que hacer.
    """
    texto = (texto or "").strip()
    if not texto:
        return None
    try:
        momento = datetime.strptime(texto, "%Y-%m")
    except ValueError:
        return None
    return momento.year, momento.month


def rango_del_mes(anio, mes):
    """El primer y el ultimo dia de ese mes, como (date, date).

    El ultimo dia sale de monthrange y no de una constante por mes: febrero
    cambia de largo segun el anio, y restarle un dia al primero del mes
    siguiente obliga a manejar el salto de diciembre a enero a mano.
    """
    return date(anio, mes, 1), date(anio, mes, monthrange(anio, mes)[1])


def en_rango(query, desde, hasta):
    """Eventos entre dos fechas, ambas incluidas, en orden de calendario.

    No filtra por "todavia no paso", a diferencia de proximos(): el calendario
    del home tiene navegacion de meses, y si escondiera lo ya vencido, moverse
    a un mes anterior mostraria un mes vacio y la navegacion no serviria de
    nada. Tampoco lo hace dentro del mes en curso: un calendario de agosto
    parado un 20 tiene que seguir mostrando la feria del 14, porque lo que
    responde es "que paso y que va a pasar este mes", no "a que llego a ir".

    El orden y el desempate por id son los mismos que en proximos() y por la
    misma razon (ver su docstring): la hora es opcional, asi que varios eventos
    del mismo dia comparten la clave de orden entera.
    """
    return (
        query.filter(Event.fecha >= desde, Event.fecha <= hasta)
        .order_by(Event.fecha.asc(), Event.hora.asc(), Event.id.asc())
    )



# ------------------------------------------------- los filtros de la cartelera

def tipo_valido(texto):
    """El tipo de TiposEvento que nombra ese texto, o None.

    Devuelve None tanto si viene vacio como si viene basura, y las dos cosas
    significan lo mismo para quien filtra: "todos". Mismo criterio que
    blog.reglas.categoria_valida -- un ?tipo= inventado a mano no revienta la
    pantalla, se ignora.
    """
    texto = (texto or "").strip().lower()
    return texto if texto in TiposEvento.TODOS else None


def del_dia(query, dia):
    """Los eventos de una fecha exacta.

    Es el filtro que gana el calendario de la cartelera al dejar de ser una
    ilustracion: hasta ahora pintaba los dias con eventos y ahi terminaba.

    Sin corte de "ya paso", igual que en_rango() y por lo mismo: si escondiera
    lo vencido, elegir un dia del pasado en el calendario mostraria un dia vacio
    y el calendario no serviria para mirar para atras.
    """
    return query.filter(Event.fecha == dia).order_by(
        Event.hora.asc(), Event.id.asc()
    )


def filtrar(query, tipo=None, solo_libres=False):
    """Aplica los dos filtros de la barra de la cartelera, si vienen.

    `tipo` ya tiene que venir validado (ver tipo_valido): esto no valida, filtra.

    UN EVENTO SIN TIPO NO APARECE EN NINGUN FILTRO POR TIPO, y es lo correcto:
    `tipo` es nullable porque los eventos cargados antes de la columna no lo
    tienen (ver models/event.py), y NULL es "no lo dijo", no "es de todos los
    tipos". Con "Todos" -- que es no pasar tipo -- siguen apareciendo.

    Los dos filtros se combinan con AND y no se excluyen: "talleres con entrada
    libre" es exactamente la pregunta que alguien hace parado en la cartelera.
    """
    if tipo:
        query = query.filter(Event.tipo == tipo)
    if solo_libres:
        query = query.filter(Event.entrada_libre.is_(True))
    return query


def eventos_de_usuario(user_id):
    """Query base con los eventos de todos los emprendimientos de un usuario.

    Los eventos cuelgan del emprendimiento, no del usuario, asi que el perfil
    (que es de la persona) tiene que pasar por posts para juntarlos.
    """
    return Event.query.join(Post, Post.id == Event.post_id).filter(Post.author == user_id)
