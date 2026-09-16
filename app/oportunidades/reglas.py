"""Las decisiones de las oportunidades, sin saber que existe HTTP.

Nada de aca toca request, flash ni db.session: son preguntas que se contestan
con lo que ya se trajo de la base, para que se puedan probar sueltas y para que
las vistas queden siendo HTTP y nada mas.

PERMISOS ASIMETRICOS, que es lo que hay que tener presente leyendo este
archivo. Publicar una oportunidad lo puede hacer CUALQUIER USUARIO con el
perfil completo (telefono y ubicacion); mandar una propuesta solo alguien que
tenga un EMPRENDIMIENTO, y la manda desde ese emprendimiento. Son dos criterios
distintos a proposito: pedir un servicio no requiere ser nadie, ofrecerlo si.
"""

from app.oportunidades.modelo_oportunidad import EstadosOportunidad, Oportunidad
from app.oportunidades.modelo_propuesta import MAX_PLAZO_DIAS, Propuesta
from services.perfiles import falta_de_perfil, perfil_completo
from services.validation import largo_de

# Los topes salen de las columnas y no se escriben a mano en ningun lado: son
# el mismo limite, y dos copias se despegan la primera vez que alguien agranda
# la columna. Es lo mismo que hacen app/servicios/reglas.py y
# app/personal/reglas.py.
MAX_TITULO = largo_de(Oportunidad.titulo)
MAX_DESCRIPCION = largo_de(Oportunidad.descripcion)
MAX_MENSAJE = largo_de(Propuesta.mensaje)

# El tope del plazo sale del modelo, que es el mismo numero que sostiene el
# CHECK de la columna: dos copias se despegan.
MAX_PLAZO = MAX_PLAZO_DIAS

# perfil_completo y falta_de_perfil se importan arriba, de services/perfiles.py,
# y se reexportan a proposito: es la misma regla que usa app/personal/ para
# postularse, con una sola definicion y no una copia por dominio. Aca es el
# permiso para PUBLICAR una oportunidad, no para proponer -- ver la nota de
# permisos asimetricos del docstring del modulo.


def es_autor_de(oportunidad, user_id):
    """Si esa oportunidad la publico esa persona.

    Es el permiso de todo el lado del publicador: quien ve las propuestas
    recibidas, quien acepta, quien reabre y quien finaliza. Se pregunta en el
    SERVIDOR, en cada vista, con la fila que se acaba de traer de la base;
    esconder el boton en el template no es un permiso, es una decoracion (B4).
    """
    return oportunidad is not None and oportunidad.autor_id == user_id


def es_dueño_de(post, user_id):
    """Si ese emprendimiento es de esa persona.

    Misma pregunta y mismo nombre que en app/personal/reglas.py, porque es la
    misma pregunta: lo unico que hace a alguien "emprendedor" en este proyecto
    es tener un Post.
    """
    return post is not None and post.author == user_id


def puede_publicar(user):
    """Si esa persona puede publicar una oportunidad.

    Perfil completo y nada mas: no hace falta tener un emprendimiento, porque
    el que pide un servicio no tiene por que ofrecer ninguno. El telefono y la
    ubicacion si hacen falta, y no como peaje: sin ellos, el emprendedor que
    quiera tomar el trabajo no puede contestar ni saber si le queda cerca.
    """
    return perfil_completo(user)


def recibe_propuestas(oportunidad):
    """Si esa oportunidad esta en condiciones de recibir propuestas.

    Solo abierta. Cerrada ya eligio a alguien (aunque pueda volver a abrirse) y
    finalizada se termino; en las dos, una propuesta nueva seria trabajo tirado
    para el que la escribe, que es peor que un cartel de "cerrado".
    """
    return oportunidad is not None and oportunidad.esta_abierta


def puede_proponer(oportunidad, post, user_id):
    """Si esa persona puede proponer sobre esa oportunidad desde ese post.

    Las cuatro condiciones juntas, y las cuatro del lado del servidor:

      - la oportunidad recibe propuestas (esta abierta);
      - el post es de quien esta proponiendo (es un emprendedor, y es SU
        emprendimiento y no uno que escribio en la URL);
      - el post esta PUBLICADO, no es un borrador;
      - la oportunidad no es suya.

    La tercera no es cosmetica. Ademas de que proponerse un trabajo a uno mismo
    no significa nada, el chat de este proyecto identifica la conversacion por
    (post_id, client_id) y hace abort(404) cuando client_id == post.author (ver
    views/messages.py): una propuesta del propio publicador dejaria una
    oportunidad que se puede aceptar pero cuyo chat tira 404. Se corta antes.
    """
    if not recibe_propuestas(oportunidad):
        return False
    if not es_dueño_de(post, user_id):
        return False
    # No se propone desde un borrador. Una propuesta le muestra al publicador
    # el nombre del emprendimiento del que sale, asi que proponer desde uno sin
    # publicar seria la puerta de atras para mostrarlo: el dueño todavia no
    # decidio que exista para nadie. Se corta aca y no solo en el <select> del
    # formulario, porque el post_id llega del POST y se puede escribir a mano.
    if post.es_borrador:
        return False
    return oportunidad.autor_id != post.author


def puede_ver(oportunidad, user_id):
    """Quien puede abrir la ficha de una oportunidad.

    Las abiertas y las cerradas las ve cualquiera: la cerrada sale del listado
    publico pero sigue accesible por URL, porque el que mando una propuesta
    tiene que poder volver a ver en que quedo.

    La finalizada la ve SOLO su autor, en su historial. Para el resto no existe
    mas, y eso es lo que significa el estado: se termino y no vuelve.
    """
    if oportunidad is None:
        return False
    if oportunidad.esta_finalizada:
        return es_autor_de(oportunidad, user_id)
    return True


def puede_aceptar(oportunidad, propuesta, user_id):
    """Si esa persona puede aceptar esa propuesta.

    Tiene que ser el autor, la oportunidad tiene que estar abierta y la
    propuesta tiene que ser de esa oportunidad. Lo ultimo parece obvio y no lo
    es: los dos ids llegan por la URL y nada obliga a que vayan juntos.
    """
    if not es_autor_de(oportunidad, user_id):
        return False
    if not oportunidad.esta_abierta:
        return False
    return propuesta is not None and propuesta.oportunidad_id == oportunidad.id


def puede_reabrir(oportunidad, user_id):
    """Si esa persona puede reabrir esa oportunidad.

    Solo desde cerrada. Desde finalizada no, que es toda la diferencia entre
    los dos estados.
    """
    return (
        es_autor_de(oportunidad, user_id)
        and oportunidad.estado == EstadosOportunidad.CERRADA
    )


def puede_finalizar(oportunidad, user_id):
    """Si esa persona puede finalizar esa oportunidad.

    Desde abierta o desde cerrada, indistinto: se puede dar por terminado algo
    que nunca se cerro (nadie propuso nada que sirviera) igual que algo que ya
    se resolvio. Lo unico que no se puede es finalizar dos veces.
    """
    return es_autor_de(oportunidad, user_id) and not oportunidad.esta_finalizada


def plazo_valido(dias):
    """Si el plazo es un entero de dias que tiene sentido.

    El tope sale de la constante del modelo, que es la misma que sostiene el
    CHECK: dos copias del numero se despegan.
    """
    return isinstance(dias, int) and 0 < dias <= MAX_PLAZO_DIAS


# El nombre del UNIQUE y el de la columna con su tabla: SQLite nombra la
# columna y MySQL la constraint, asi que se miran los dos. Mismo criterio y
# mismos motivos que es_activa_duplicada en app/personal/reglas.py.
_CONSTRAINT_ACEPTADA = "uq_propuestas_aceptada"
_COLUMNA_ACEPTADA = "propuestas.cupo_aceptada"


def es_aceptada_duplicada(error):
    """Si ese IntegrityError es el del UNIQUE de la unica propuesta aceptada.

    Se mira antes de dar por hecho de que error se trata: un IntegrityError a
    secas tambien lo levanta la FK del post si se borra el emprendimiento justo
    en el medio, y ahi el publicador veria "ya aceptaste una propuesta", que es
    mentira, y el error real se perderia sin dejar rastro.
    """
    texto = str(getattr(error, "orig", error))
    return _CONSTRAINT_ACEPTADA in texto or _COLUMNA_ACEPTADA in texto

