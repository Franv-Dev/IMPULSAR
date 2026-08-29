"""Las decisiones de negocio del dominio, sin saber que existe HTTP.

Ninguna funcion de aca usa request, flash, redirect ni abort: devuelven un bool
o un dato, y quien decide como se le cuenta eso al usuario es vistas.py. Esa
separacion es la que hace que las reglas se puedan leer (y probar) sin levantar
un request.
"""

from app.blog.modelo_post import MAX_IMAGENES_POR_POST, Categorias

# Los dos tipos de contenido que se pueden reportar. Viven aca y no sueltos en
# la ruta porque son el dominio de lo reportable, no un detalle de la URL.
TIPOS_REPORTABLES = ("post", "review")

# Rango de estrellas de una resenia. El mismo rango lo garantiza tambien un
# CheckConstraint en la base (ver modelo_resenia.py); esto es para poder
# rechazarlo con un mensaje antes de llegar a la base.
RATING_MINIMO = 1
RATING_MAXIMO = 5

# Los radios que ofrece la busqueda por cercania, en km. Es una lista corta y
# cerrada y no un numero libre a proposito: el filtro va al WHERE como una
# cuenta de trigonometria sobre toda la tabla, asi que aceptar cualquier valor
# es dejar que desde la URL se pidan consultas arbitrarias. Ademas la pantalla
# lo muestra como tres botones, no como un campo.
RADIOS_KM = (1, 5, 10)


def es_el_autor(post, user_id):
    """Si ese emprendimiento es de ese usuario.

    Es el permiso de editar, borrar y ver lo que esta apagado.
    """
    return post.author == user_id


def es_el_autor_de_la_resenia(resenia, user_id):
    return resenia.user_id == user_id


def puede_responder_la_resenia(resenia, user_id):
    """Responder una resenia es del dueño del emprendimiento resenado.

    Se mira el autor del post y no el de la resenia: el que contesta es el otro
    lado de la conversacion.
    """
    return resenia.post.author == user_id


def puede_resenar(post, user_id):
    """Nadie resena su propio emprendimiento."""
    return post.author != user_id


def rating_valido(rating):
    return RATING_MINIMO <= rating <= RATING_MAXIMO


def tipo_reportable(tipo):
    return tipo in TIPOS_REPORTABLES


def puede_reportar(objetivo, tipo, user_id):
    """Nadie reporta lo propio, sea un emprendimiento o una resenia."""
    if tipo == "post":
        return objetivo.author != user_id
    return objetivo.user_id != user_id


# Como se reconoce el choque contra el UNIQUE del reporte pendiente unico. Los
# dos motores dicen algo distinto: MySQL nombra la constraint ("Duplicate entry
# '3-p7' for key 'uq_reports_pendiente'") y SQLite no la nombra, lista las
# columnas ("UNIQUE constraint failed: reports.reporter_id, ..."), asi que se
# buscan las dos formas. clave_pendiente no participa de ninguna otra
# constraint, asi que alcanza para distinguirla.
_CONSTRAINT_REPORTE_PENDIENTE = "uq_reports_pendiente"
_COLUMNA_REPORTE_PENDIENTE = "reports.clave_pendiente"


def es_reporte_duplicado(error):
    """Si ese IntegrityError es el del UNIQUE del reporte pendiente unico.

    Se mira antes de dar por hecho de que error se trata: un IntegrityError a
    secas tambien lo levanta, por ejemplo, la FK del post si el autor lo borra
    justo en el medio, y ahi el usuario veria "ya tenes un reporte pendiente",
    que es mentira, y el error real se perderia sin dejar rastro.
    """
    texto = str(getattr(error, "orig", error))
    return (
        _CONSTRAINT_REPORTE_PENDIENTE in texto
        or _COLUMNA_REPORTE_PENDIENTE in texto
    )


def entran_las_fotos(cuantas_pide, ya_ocupados=0):
    """Si esas fotos entran en lo que le queda libre al emprendimiento."""
    return cuantas_pide + ya_ocupados <= MAX_IMAGENES_POR_POST


def lugares_libres(ya_ocupados):
    """Cuantas fotos mas acepta el emprendimiento. Nunca negativo."""
    return max(0, MAX_IMAGENES_POR_POST - ya_ocupados)


def radio_valido(radio):
    """Si ese radio es uno de los que se ofrecen."""
    return radio in RADIOS_KM


def categoria_valida(categoria):
    """Si es una de las categorias de la lista.

    La categoria llega de un <select>, pero se valida igual: el POST se puede
    mandar a mano con cualquier cosa, y una categoria invalida dejaria el
    emprendimiento fuera del filtro por categoria sin que nadie se entere.
    """
    return categoria in Categorias.TODAS


# --------------------------------------------------- checklist de publicacion

# Cuanto tiene que tener una descripcion para contar como completa. No es un
# limite de la base (Post.body es Text y no valida largo) sino un consejo: mas
# corto que esto no alcanza para que alguien entienda que ofrece el
# emprendimiento. Vive aca y no en el template para que el numero se diga una
# sola vez, en el item y en el texto de ayuda.
DESCRIPCION_COMPLETA = 120

# Cuantas fotos ademas de la principal se recomiendan.
FOTOS_RECOMENDADAS = 2


def checklist_de_publicacion(post, tiene_horarios):
    """Que le falta a un emprendimiento para estar bien cargado.

    Es un consejo y no una validacion: un emprendimiento se publica con el
    nombre y la descripcion, y todo lo demas se puede completar despues. Por
    eso no corta nada ni vive en formulario.py.

    Devuelve una lista de dicts {etiqueta, cumplido}. Dicts y no tuplas para
    que el template pueda contar los cumplidos con un selectattr("cumplido"),
    que sobre tuplas no funciona.

    `post` es None en el alta, que es el caso en el que todavia no hay nada que
    cumplir: los items salen todos sin tildar menos los horarios, que son del
    usuario y no del emprendimiento y pueden estar cargados de antes.

    `tiene_horarios` se pasa y no se consulta adentro por lo mismo que el resto
    de este modulo: aca no se toca la base.
    """
    galeria = len(post.imagenes) if post else 0

    items = [
        ("Nombre y categoría", bool(post and post.title and post.category)),
        (
            f"Descripción de al menos {DESCRIPCION_COMPLETA} caracteres",
            bool(post and post.body and len(post.body) >= DESCRIPCION_COMPLETA),
        ),
        ("Foto principal", bool(post and post.image)),
        (
            f"{FOTOS_RECOMENDADAS} fotos más (te encuentran más veces)",
            galeria >= FOTOS_RECOMENDADAS,
        ),
        ("Horarios de atención", bool(tiene_horarios)),
        ("Dirección", bool(post and post.address_street)),
    ]
    return [{"etiqueta": etiqueta, "cumplido": cumplido} for etiqueta, cumplido in items]
