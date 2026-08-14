"""Eventos y ferias: fechas, corte de "ya paso" y consultas compartidas.

La fecha de un evento es hora local de Argentina, no UTC: la misma distincion
que ya hacen los horarios de atencion (ver services/horarios.py), y por eso se
reusa su ZONA_ARGENTINA en vez de definir otro offset.

El corte de "todavia no paso" vive aca y no en cada vista porque lo usan el
perfil y la cartelera: si cada uno lo escribiera por su cuenta, alcanzaria con
que uno de los dos usara utcnow para que un evento aparezca vencido en una
pantalla y vigente en la otra.
"""

from datetime import datetime

from models.event import Event
from models.post import Post
from services.horarios import ZONA_ARGENTINA


# Los nombres de los meses van escritos y no salen de strftime("%B"): eso
# depende del locale del sistema operativo, que en el servidor puede estar en
# ingles y dejar "13 de September" en pantalla.
MESES = (
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
)


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


def eventos_de_usuario(user_id):
    """Query base con los eventos de todos los emprendimientos de un usuario.

    Los eventos cuelgan del emprendimiento, no del usuario, asi que el perfil
    (que es de la persona) tiene que pasar por posts para juntarlos.
    """
    return Event.query.join(Post, Post.id == Event.post_id).filter(Post.author == user_id)
