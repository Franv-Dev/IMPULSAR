"""Las decisiones de negocio del dominio, sin saber que existe HTTP.

Ninguna funcion de aca usa request, flash, redirect ni abort: devuelven un bool
o un dato, y quien decide como se le cuenta eso al usuario es vistas.py. Esa
separacion es la que hace que las reglas se puedan leer (y probar) sin levantar
un request.
"""

from app.servicios.modelo import MAX_SERVICIOS_POR_POST, Rubros
from app.servicios.modelo_solicitud import EstadosSolicitud
from app.servicios.modelo_verificacion import EstadosVerificacion


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


def rubro_valido(rubro):
    """Si es uno de los rubros del catalogo.

    Mismo criterio que blog.reglas.categoria_valida: el rubro llega de un
    <select>, pero la URL se escribe a mano. Un rubro que no existe no filtra
    nada en vez de cortar con un 400.
    """
    return rubro in Rubros.TODOS


# Los limites de la duracion de un turno, en minutos. Van aca y no en modelo.py
# junto a MAX_SERVICIOS_POR_POST porque no son un limite de la base sino una
# decision de negocio que el formulario tiene que poder citar en su mensaje de
# error; es el mismo lugar y el mismo criterio que RATING_MINIMO/RATING_MAXIMO
# en app/blog/reglas.py.
#
# El piso son 5 minutos: mas corto que eso no es un turno que alguien atienda,
# y ademas una jornada de 8 horas cortada en tramos de 1 minuto son 480 slots
# para pintar en una sola pantalla. El techo son 480 (8 horas), que es una
# jornada entera: un turno mas largo que el horario de atencion no genera
# ningun slot y solo se veria como "no hay turnos disponibles" sin explicacion.
MIN_DURACION_TURNO_MINUTOS = 5
MAX_DURACION_TURNO_MINUTOS = 480


def duracion_de_turno_valida(turnos_habilitados, duracion):
    """Si la duracion que mando el vendedor sirve para ese servicio.

    Con los turnos apagados no se mira nada: la columna queda en NULL y no
    significa nada (ver Service.duracion_turno_minutos). Con los turnos
    prendidos pasa a ser obligatoria y tiene que caer dentro del rango, porque
    es lo unico de lo que sale el corte de slots.

    Es una funcion y no un CHECK de la base a proposito: la condicion depende
    de OTRA columna, y un CHECK condicional recien lo valida MySQL desde 8.0.16
    (antes lo parsea y lo ignora, en silencio). Ademas mover el rango pediria
    una migracion.
    """
    if not turnos_habilitados:
        return True
    return (
        duracion is not None
        and MIN_DURACION_TURNO_MINUTOS <= duracion <= MAX_DURACION_TURNO_MINUTOS
    )


def acepta_turnos(servicio):
    """Si sobre ese servicio se puede reservar un turno.

    Las dos condiciones juntas y no solo el flag: un servicio con
    turnos_habilitados=True pero sin duracion no tiene de donde cortar slots.
    La combinacion no deberia existir (el formulario no la deja guardar), pero
    una fila cargada antes de esta tanda o tocada a mano si puede tenerla, y el
    corte de slots la tiene que poder descartar sin romperse.
    """
    return bool(servicio.turnos_habilitados) and bool(servicio.duracion_turno_minutos)


def esta_cerrada(solicitud):
    return solicitud.estado == EstadosSolicitud.CERRADA


def puede_ver_la_verificacion(verificacion, user_id, es_admin):
    """Quien puede mirar el documento de un pedido de verificacion.

    El dueño del emprendimiento del servicio (mando su propia matricula) y
    cualquier admin (es el que la tiene que revisar). Es el mismo criterio con
    el que views/admin.py arma la cola, escrito una sola vez para que la pagina
    y el archivo no puedan separarse.

    Aca si entra el admin, al reves que en es_parte_de_la_solicitud: una
    solicitud de presupuesto es privada entre dos usuarios y el admin no pinta
    nada, pero una verificacion existe justamente para que un admin la mire.

    es_admin viene como bool y no se deduce del user_id adentro para no traer
    el modelo de usuarios ni una consulta a este modulo, que no sabe de HTTP ni
    de sesiones: quien llama ya tiene el usuario en la mano.
    """
    return es_admin or verificacion.servicio.post.author == user_id


def esta_verificacion_pendiente(verificacion):
    """Si ese pedido de verificacion todavia lo tiene que mirar un admin."""
    return verificacion.estado == EstadosVerificacion.PENDIENTE


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


# Lo mismo para el UNIQUE de la verificacion pendiente. Son constantes aparte y
# no una funcion generica con la tabla por parametro porque el nombre de la
# tabla es justamente lo que distingue un choque del otro: las dos columnas se
# llaman cupo_pendiente, y SQLite las nombra con el prefijo de su tabla.
_CONSTRAINT_VERIFICACION = "uq_verification_requests_pendiente"
_COLUMNA_VERIFICACION = "verification_requests.cupo_pendiente"


def es_verificacion_duplicada(error):
    """Si ese IntegrityError es el del UNIQUE de la verificacion pendiente.

    Mismo criterio que es_pendiente_duplicada, y por el mismo motivo: cualquier
    otra violacion de integridad no es este caso y no se disfraza de este caso.
    """
    texto = str(getattr(error, "orig", error))
    return _CONSTRAINT_VERIFICACION in texto or _COLUMNA_VERIFICACION in texto


# ------------------------------------------------- resumen del panel de solicitudes

def _promedio_legible(segundos):
    """Un promedio en segundos escrito como lo diria una persona.

    Devuelve None si no hay con que promediar, para que la vista no muestre un
    "0 min" que en realidad significa "todavia no respondiste nada".
    """
    if not segundos:
        return None

    minutos = int(segundos // 60)
    if minutos < 60:
        return f"{max(minutos, 1)} min"

    horas = minutos // 60
    if horas < 48:
        return f"{horas} h"

    return f"{horas // 24} d"


def resumen_de_solicitudes(recibidas, ahora):
    """Los tres numeros del "Cómo vas" del panel, derivados de la lista.

    No hace consultas a proposito: `recibidas` ya viene entera de
    consultas.solicitudes_recibidas_por(), asi que contar en Python es gratis y
    tres COUNT/AVG mas contra la misma tabla no son. Si algun dia el listado se
    pagina, esto pasa a ser una consulta y deja de recibir la lista.

    `ahora` se pasa y no se toma de utcnow() adentro para que el corte del mes
    se pueda probar sin viajar en el tiempo.

    "Respondidas este mes" es el mes calendario corriente y no los ultimos 30
    dias: el numero lo lee alguien que quiere saber como viene ESTE mes, y una
    ventana movil cambia de valor todos los dias sin que haya pasado nada.
    """
    pendientes = 0
    respondidas_del_mes = 0
    demoras = []

    for solicitud in recibidas:
        if solicitud.estado == EstadosSolicitud.PENDIENTE:
            pendientes += 1

        if solicitud.responded_at:
            if (solicitud.responded_at.year, solicitud.responded_at.month) == (
                ahora.year, ahora.month
            ):
                respondidas_del_mes += 1

            if solicitud.created_at:
                demoras.append(
                    (solicitud.responded_at - solicitud.created_at).total_seconds()
                )

    return {
        "pendientes": pendientes,
        "respondidas_del_mes": respondidas_del_mes,
        "promedio": _promedio_legible(sum(demoras) / len(demoras) if demoras else 0),
    }
