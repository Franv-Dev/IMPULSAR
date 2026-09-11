"""Las decisiones de la busqueda de personal, sin saber que existe HTTP.

Nada de aca toca request, flash ni db.session: son preguntas que se contestan
con lo que ya se trajo de la base, para que se puedan probar sueltas y para que
las vistas queden siendo HTTP y nada mas.
"""

from app.personal.modelo_busqueda import BusquedaPersonal, Modalidades
from app.personal.modelo_postulacion import Postulacion
from services.validation import largo_de

# Los topes salen de las columnas y no se escriben a mano en ningun lado: son
# el mismo limite, y dos copias se despegan la primera vez que alguien agranda
# la columna. Es lo mismo que hace app/servicios/reglas.py.
MAX_PUESTO = largo_de(BusquedaPersonal.puesto)
MAX_DESCRIPCION = largo_de(BusquedaPersonal.descripcion)
MAX_NOMBRE = largo_de(Postulacion.nombre)
MAX_CONTACTO = largo_de(Postulacion.contacto)
MAX_EXPERIENCIA = largo_de(Postulacion.experiencia)
MAX_DISPONIBILIDAD = largo_de(Postulacion.disponibilidad)


def es_dueño_de(post, user_id):
    """Si ese emprendimiento es de esa persona.

    Es el unico criterio de permiso de todo el dominio: quien prende el toggle,
    quien ve la bandeja de postulantes y quien abre el chat es el dueño del
    emprendimiento. Se pregunta en el SERVIDOR, en cada vista; esconder el
    boton en el template no es un permiso, es una decoracion (B4).
    """
    return post is not None and post.author == user_id


def es_dueño_de_la_busqueda(busqueda, user_id):
    """Lo mismo, un nivel mas adentro: el dueño del post del que cuelga."""
    return busqueda is not None and es_dueño_de(busqueda.post, user_id)


def modalidad_valida(modalidad):
    """Si la modalidad es una de las del catalogo.

    Llega de un <select>, pero se valida igual: el POST se puede mandar a mano
    con cualquier cosa, y una modalidad invalida dejaria el aviso fuera de
    cualquier filtro futuro sin que nadie se entere. Mismo criterio que
    rubro_valido.
    """
    return modalidad in Modalidades.TODAS


# Que significa "perfil completo" para poder postularse. Telefono y ubicacion,
# y no el perfil entero: son los dos datos sin los cuales el emprendedor no
# puede contestarle a nadie ni saber si le sirve por distancia. Pedir mas
# (bio, avatar, redes) seria un peaje que no ayuda a la decision.
CAMPOS_DE_PERFIL_COMPLETO = ("phone", "location")


def perfil_completo(user):
    """Si esa persona tiene lo minimo cargado para postularse.

    Vacio y NULL cuentan igual: un telefono que es "   " no es un telefono. Por
    eso se compara el strip() y no la presencia de la columna.
    """
    if user is None:
        return False
    return all(
        (getattr(user, campo, None) or "").strip()
        for campo in CAMPOS_DE_PERFIL_COMPLETO
    )


def falta_para_postularse(user):
    """Que campos le faltan, para poder decirselo con nombre y no en general."""
    etiquetas = {"phone": "el teléfono", "location": "la ubicación"}
    return [
        etiquetas[campo]
        for campo in CAMPOS_DE_PERFIL_COMPLETO
        if not (getattr(user, campo, None) or "").strip()
    ]


def puede_postularse(busqueda, user_id):
    """Si esa persona puede postularse a esa busqueda, mirando solo la busqueda.

    El perfil completo y el duplicado se preguntan aparte porque cada uno
    termina en una pantalla distinta (completar perfil / la postulacion que ya
    mando). Aca queda lo que depende de la busqueda misma: existe, esta activa
    y no es del propio dueño, que no se postula a su propio aviso.
    """
    if busqueda is None or not busqueda.activa:
        return False
    return not es_dueño_de_la_busqueda(busqueda, user_id)


# El nombre del UNIQUE y el de la columna con su tabla: SQLite nombra la
# columna y MySQL la constraint, asi que se miran los dos. Mismo criterio y
# mismos motivos que es_pendiente_duplicada en app/servicios/reglas.py.
_CONSTRAINT_ACTIVA = "uq_busquedas_personal_activa"
_COLUMNA_ACTIVA = "busquedas_personal.cupo_activa"


def es_activa_duplicada(error):
    """Si ese IntegrityError es el del UNIQUE de la unica busqueda activa.

    Se mira antes de dar por hecho de que error se trata: un IntegrityError a
    secas tambien lo levanta la FK del post si se borra el emprendimiento justo
    en el medio, y ahi el emprendedor veria "ya tenes una busqueda activa", que
    es mentira, y el error real se perderia sin dejar rastro.
    """
    texto = str(getattr(error, "orig", error))
    return _CONSTRAINT_ACTIVA in texto or _COLUMNA_ACTIVA in texto


_CONSTRAINT_POSTULACION = "uq_postulaciones_una_por_busqueda"
_COLUMNA_POSTULACION = "postulaciones.postulante_id"


def es_postulacion_duplicada(error):
    """Si ese IntegrityError es el del UNIQUE de una postulacion por busqueda."""
    texto = str(getattr(error, "orig", error))
    return _CONSTRAINT_POSTULACION in texto or _COLUMNA_POSTULACION in texto
