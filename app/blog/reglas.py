"""Las decisiones de negocio del dominio, sin saber que existe HTTP.

Ninguna funcion de aca usa request, flash, redirect ni abort: devuelven un bool
o un dato, y quien decide como se le cuenta eso al usuario es vistas.py. Esa
separacion es la que hace que las reglas se puedan leer (y probar) sin levantar
un request.
"""

from functools import lru_cache

from sqlalchemy import exists
from sqlalchemy.orm import aliased

from app.blog.modelo_post import (
    MAX_IMAGENES_POR_POST, Categorias, EstadosPost, Post,
)

# Largo maximo del nombre de un emprendimiento. Sale de la columna y no de un
# numero escrito a mano: son el mismo limite, y dos copias se despegan la
# primera vez que alguien agranda la columna.
#
# Hace falta chequearlo antes del INSERT y no confiar en que la base corte:
# MySQL trunca o falla segun el sql_mode con el que este levantado, asi que sin
# esto un nombre largo o se guarda cortado a la mitad sin avisar, o muere con
# un DataError que nadie atrapa y el usuario ve como un 500 en vez de como un
# error del formulario. Es el mismo caso que MAX_USERNAME_LENGTH en
# services/validation.py.
MAX_TITULO = Post.title.type.length

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


class OrdenesFavoritos:
    """Como se puede ordenar la pantalla "Mis favoritos".

    Una clase de constantes con su tupla y su dict de etiquetas, igual que
    Categorias y que Roles: los strings viven en un solo lugar y el <select>
    del template se arma del mismo lado del que se valida lo que llega, asi
    que no se pueden despegar.

    RECIENTE es el default y ordena por cuando se marco el favorito, no por
    cuando se publico el emprendimiento: la pantalla es la lista de marcas del
    usuario, y lo ultimo que marco es lo que viene a buscar.

    NOMBRE existe porque la otra forma de usar esta pantalla es al reves: no
    "que guarde recien" sino "donde esta aquel que se llamaba algo con P", y
    para eso el orden por fecha no ayuda.
    """

    RECIENTE = "reciente"
    NOMBRE = "nombre"

    TODOS = (RECIENTE, NOMBRE)

    ETIQUETAS = {
        RECIENTE: "Agregados recientemente",
        NOMBRE: "Nombre (A-Z)",
    }


@lru_cache(maxsize=1)
def _post_del_exists():
    """El post visto desde adentro del EXISTS de de_post_publicado().

    UNO SOLO PARA TODA LA APP, y por eso esta memoizado: un aliased() nuevo por
    llamada le cambia la cache key a cada consulta que lo use, asi que SQLAlchemy
    no puede reusar la sentencia compilada. Medido: 725 ms contra 266 ms por 300
    consultas.

    Y ES PEREZOSO en vez de una constante de modulo porque aliased() configura
    los mappers, y a la hora del import de este archivo todavia no estan todos
    los modelos cargados: puesto arriba, revienta con "expression 'User' failed
    to locate a name". lru_cache da las dos cosas -- se arma en la primera
    consulta, y desde ahi es siempre el mismo objeto --.
    """
    return aliased(Post)


def es_publicado():
    """La condicion de "este emprendimiento existe para el resto del mundo".

    Una funcion y no la expresion suelta para que el string del estado no quede
    escrito en quince consultas: el dia que haya un tercer estado que tambien
    sea publico (un "destacado", por ejemplo), se agrega aca y no hay que
    acordarse de las quince.
    """
    return Post.estado == EstadosPost.PUBLICADO


def solo_publicados(consulta):
    """Le saca los borradores a una consulta que YA tiene posts adentro.

    Para las consultas cuya entidad es Post, o que ya lo trajeron con un join
    (el catalogo de productos, la busqueda de servicios). Cuando el post no
    esta en la consulta, la condicion se escribe con de_post_publicado() para
    no sumar un join.

    POR QUE NO VA ADENTRO DE query_posts_con_rating NI DE UN default_scope. Es
    tentador: ese helper lo usan las tres pantallas publicas que listan posts y
    quedaria cubierto de una. Pero el mismo helper tendria que servir para "Mis
    emprendimientos", que es la unica pantalla que SI tiene que ver los
    borradores, y un filtro implicito que hay que recordar apagar es peor que
    uno explicito que hay que recordar poner: el primero falla mostrando de
    menos --el dueño no encuentra su propio borrador y no sabe por que-- y el
    segundo falla en un test.
    """
    return consulta.filter(es_publicado())


@lru_cache(maxsize=None)
def de_post_publicado(columna_post_id):
    """La misma condicion, para las filas que CUELGAN de un emprendimiento.

    `columna_post_id` es la FK al post (Service.post_id, Product.post_id,
    Event.post_id). Devuelve un EXISTS correlacionado y no un join, por dos
    motivos:

      - no le cambia la forma a la consulta de quien llama. Hay consultas que
        ya traen posts con un join y otras que no lo traen para nada (el GROUP
        BY del contador por rubro de servicios), y un filtro sobre una tabla
        que no esta en el FROM se la agrega SIN condicion de join, o sea un
        producto cartesiano que multiplica los conteos en silencio;
      - las que si traen el post lo hacen muchas veces con joinedload, que
        arma su propio LEFT JOIN con alias: un join a mano dejaria posts dos
        veces en el SELECT.

    Va sobre la FK y no sobre la relationship (`Service.post.has(...)`, que
    seria mas corto) porque el backref `post` lo crea el mapper de Post al
    configurarse, y esto se evalua al armar la consulta: con los mappers
    todavia sin configurar, `Service.post` es un AttributeError. La FK es una
    columna del propio modelo y siempre esta.

    EL ALIAS NO ES DECORATIVO, y es lo que hay que entender para no romperlo.
    Adentro del EXISTS el post va aliaseado porque algunas de las consultas que
    usan esto YA tienen posts en su FROM (la busqueda de servicios lo joinea
    para pintar el nombre del emprendimiento). Sin alias, SQLAlchemy
    autocorrelaciona las DOS tablas del subselect --posts y services-- y el
    subselect se queda sin FROM: InvalidRequestError, "returned no FROM clauses
    due to auto-correlation". Con el alias, la tabla de adentro es otra, asi que
    lo unico que correlaciona es la FK de afuera, que es justo lo que se quiere.

    Y EL ALIAS ES UNO SOLO, DE MODULO, no uno nuevo por llamada. Esto se midio:
    un aliased(Post) por llamada hace que cada consulta tenga una cache key
    distinta, asi que SQLAlchemy no puede reusar la sentencia compilada y la
    recompila entera cada vez. Son 725 ms contra 266 ms por 300 consultas, o sea
    casi tres veces mas caro, y se paga en cada request y no solo en los tests.
    Reusarlo es seguro porque un alias es una construccion inmutable y cada
    EXISTS es su propio scope: dos subconsultas con el mismo alias no se pisan.
    Vive en _post_del_exists(), memoizado y perezoso -- ver ahi por que no puede
    ser una constante de modulo.

    Y ESTA FUNCION TAMBIEN ESTA MEMOIZADA, por lo mismo: la condicion armada es
    inmutable y los argumentos son atributos de clase (Product.post_id y
    compania), o sea un puñado de valores fijos. Devolver siempre el mismo objeto
    ahorra rearmar el EXISTS en cada request y termina de cerrar la diferencia:
    725 ms -> 337 ms con el alias memoizado -> 222 ms memoizando tambien esto.

    El EXISTS correlaciona por la PK de posts, que esta indexada, asi que es la
    forma barata de preguntarlo: lo que sale caro es correlacionar sobre una
    expresion que ningun indice puede sostener, y esto es la PK.
    """
    post = _post_del_exists()
    return exists().where(post.id == columna_post_id).where(
        post.estado == EstadosPost.PUBLICADO
    )


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


# ------------------------------------------------------ orden de las fotos

# Como viaja "la foto principal" en el formulario de reordenar. Las demas
# viajan con el id de su fila de post_images, que es un numero, asi que esta
# palabra no puede chocar con ninguna.
#
# Hace falta un token propio porque la principal NO es una fila de
# post_images: vive en Post.image (ver modelo_imagen.py), asi que no tiene id
# con el cual nombrarse.
TOKEN_PRINCIPAL = "principal"


def tokens_de_fotos(post):
    """Los identificadores de las fotos del post, en el orden en que se ven.

    Sale en el mismo orden que post.galeria, asi que los dos se recorren juntos
    para saber que archivo es cada token.
    """
    tokens = [TOKEN_PRINCIPAL] if post.image else []
    return tokens + [str(imagen.id) for imagen in post.imagenes]


def orden_de_fotos_valido(post, tokens):
    """Si esa lista es una reordenacion legitima de las fotos que tiene el post.

    Tiene que ser una permutacion exacta: las mismas fotos, cada una una sola
    vez. Nada de faltantes (seria un borrado encubierto), nada de repetidas
    (duplicaria un archivo y perderia otro) y nada de tokens ajenos (podria
    robar la fila de post_images de OTRO emprendimiento, que es de otro dueño).

    Se valida aca y no confiando en el formulario porque el POST se manda a
    mano con lo que sea; esta ruta escribe datos del usuario.
    """
    if not tokens:
        return False
    if len(set(tokens)) != len(tokens):
        return False
    return sorted(tokens) == sorted(tokens_de_fotos(post))


def _con_token_movido(tokens, desde, hasta):
    """La misma lista con el elemento de `desde` reubicado en `hasta`."""
    movido = list(tokens)
    movido.insert(hasta, movido.pop(desde))
    return movido


def fotos_para_reordenar(post):
    """Las fotos del post con todo lo que el formulario necesita por cada una.

    Cada item trae, ademas del archivo y su token, el orden COMPLETO que
    resultaria de cada movimiento posible. Eso es lo que deja que los botones
    funcionen sin una linea de JavaScript: cada boton es un submit que ya lleva
    el resultado calculado, en vez de una instruccion que el servidor tendria
    que interpretar. El drag and drop escribe en el mismo campo, asi que la
    ruta recibe una sola forma de dato y no dos.

    Devuelve dicts y no tuplas para que el template los lea por nombre.
    """
    tokens = tokens_de_fotos(post)
    nombres = post.galeria
    ultimo = len(tokens) - 1

    return [
        {
            "token": token,
            "filename": nombre,
            "es_principal": posicion == 0,
            "posicion": posicion,
            # None cuando el movimiento no existe: el template no dibuja ese
            # boton en vez de dibujarlo apagado, que seria un control que no
            # hace nada.
            "orden_subiendo": (
                _con_token_movido(tokens, posicion, posicion - 1)
                if posicion > 0 else None
            ),
            "orden_bajando": (
                _con_token_movido(tokens, posicion, posicion + 1)
                if posicion < ultimo else None
            ),
            "orden_como_principal": (
                _con_token_movido(tokens, posicion, 0) if posicion > 0 else None
            ),
        }
        for posicion, (token, nombre) in enumerate(zip(tokens, nombres))
    ]


def radio_valido(radio):
    """Si ese radio es uno de los que se ofrecen."""
    return radio in RADIOS_KM


def orden_de_favoritos_valido(orden):
    """Si es uno de los ordenes que ofrece la pantalla.

    Se valida por lo mismo que la categoria: llega de un <select> pero viaja
    en la URL, y cualquiera puede escribir ahi otra cosa. Lo que no se valida
    aca es que hacer con lo invalido -- eso lo decide quien llama, y en esta
    pantalla es caer al default en vez de fallar.
    """
    return orden in OrdenesFavoritos.TODOS


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
