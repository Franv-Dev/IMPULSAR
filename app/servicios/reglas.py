"""Las decisiones de negocio del dominio, sin saber que existe HTTP.

Ninguna funcion de aca usa request, flash, redirect ni abort: devuelven un bool
o un dato, y quien decide como se le cuenta eso al usuario es vistas.py. Esa
separacion es la que hace que las reglas se puedan leer (y probar) sin levantar
un request.
"""

from app.servicios.modelo import MAX_SERVICIOS_POR_POST
from app.servicios.modelo_solicitud import EstadosSolicitud


def es_de(servicio, user_id):
    """Si ese servicio cuelga de un emprendimiento de ese usuario.

    El permiso se resuelve mirando el dueño del emprendimiento y no un campo
    del servicio: un servicio pertenece a un Post, no a un usuario.
    """
    return servicio.post.author == user_id


def es_parte_de_la_solicitud(solicitud, user_id):
    """Las dos personas que pueden ver una solicitud: el cliente y el prestador.

    Nadie mas, ni otro emprendedor ni un admin.
    """
    return user_id in (solicitud.cliente_id, solicitud.servicio.post.author)


def es_el_prestador(solicitud, user_id):
    """Quien puede responder: el dueño del emprendimiento del servicio.

    El cliente es parte de la solicitud y la ve entera, pero la respuesta viene
    del otro lado.
    """
    return solicitud.servicio.post.author == user_id


def hay_lugar(cuantos_tiene):
    """Si entra un servicio mas en ese emprendimiento."""
    return cuantos_tiene < MAX_SERVICIOS_POR_POST


def esta_cerrada(solicitud):
    return solicitud.estado == EstadosSolicitud.CERRADA


# Como se reconoce el choque contra el UNIQUE de la pendiente unica. Los dos
# motores dicen algo distinto: MySQL nombra la constraint ("Duplicate entry
# '1-2-1' for key 'uq_service_requests_pendiente'") y SQLite no la nombra, lista
# las columnas ("UNIQUE constraint failed: service_requests.service_id, ..."),
# asi que se buscan las dos formas. cupo_pendiente no participa de ninguna otra
# constraint, asi que alcanza para distinguirla.
_CONSTRAINT_PENDIENTE = "uq_service_requests_pendiente"
_COLUMNA_PENDIENTE = "service_requests.cupo_pendiente"


def es_pendiente_duplicada(error):
    """Si ese IntegrityError es el del UNIQUE de la pendiente unica.

    Se mira antes de dar por hecho de que error se trata: un IntegrityError a
    secas tambien lo levanta, por ejemplo, la FK del servicio si el prestador lo
    borra justo en el medio, y ahi el cliente veria "ya tenes una solicitud
    pendiente", que es mentira, y el error real se perderia sin dejar rastro.
    """
    texto = str(getattr(error, "orig", error))
    return _CONSTRAINT_PENDIENTE in texto or _COLUMNA_PENDIENTE in texto
