"""Todo lo que este dominio le pregunta a la base.

Es la unica capa que arma querys. Las vistas no tocan db.session: piden por
nombre lo que necesitan, y si mañana una consulta necesita otro joinedload u
otro orden, se cambia aca sin abrir ninguna ruta.

El listado publico es el caso mas grande: filtros por texto, por categoria y por
cercania, mas la paginacion. Se arma entero aca y la vista recibe la pagina ya
resuelta, porque cada uno de esos filtros es una decision sobre la consulta, no
sobre la pantalla.
"""

from sqlalchemy import and_, case, func, or_

from app.blog import reglas
from app.blog.modelo_favorito import Favorite
from app.blog.modelo_post import Post
from app.blog.modelo_reporte import Report
from app.blog.modelo_resenia import Review
from app.perfil.modelo_horario import Horario
from app.servicios.modelo import Service
from db import db
from models.product import Product
from services.horarios import ventana_actual
from services.ratings import query_posts_con_rating


def post_por_id_o_404(id):
    return Post.query.get_or_404(id)


def post_por_id(id):
    """Sin el 404 automatico: para quien quiera decidir el mensaje del faltante."""
    return Post.query.get(id)


def resenia_por_id_o_404(id):
    return Review.query.get_or_404(id)


def ids_favoritos(user_id):
    """IDs de los posts que el usuario marco como favoritos, en una sola consulta."""
    filas = db.session.query(Favorite.post_id).filter_by(user_id=user_id).all()
    return {post_id for (post_id,) in filas}


def _distancia_km(lat, lon):
    """Expresion SQL: distancia en km entre (lat, lon) y cada Post.

    Formula del semiverseno resuelta con funciones matematicas de MySQL, para
    que el ORDER BY y la paginacion los siga resolviendo la base de datos en
    vez de traer todos los posts a Python para ordenarlos ahi.
    """
    argumento = (
        func.cos(func.radians(lat)) * func.cos(func.radians(Post.latitude)) *
        func.cos(func.radians(Post.longitude) - func.radians(lon)) +
        func.sin(func.radians(lat)) * func.sin(func.radians(Post.latitude))
    )
    # Buscar cerca de un post con las mismas coordenadas puede dar, por
    # redondeo de punto flotante, un argumento apenas fuera de [-1, 1]; ACOS()
    # de eso es NULL. Se acota con CASE (no LEAST/GREATEST: no existen en
    # SQLite, que es lo que usan los tests).
    argumento_acotado = case(
        (argumento > 1, 1),
        (argumento < -1, -1),
        else_=argumento,
    )
    return 6371 * func.acos(argumento_acotado)


def _abierto_ahora_sql(ahora=None):
    """EXISTS que deja solo los posts cuyo autor esta atendiendo en este momento.

    Es la misma regla de services.horarios.esta_abierto() escrita en SQL, y va
    en SQL a proposito: resuelto en Python habria que traer los horarios de
    cada fila (un SELECT por emprendimiento, el N+1 clasico) y ademas filtrar
    despues de paginar, con lo cual el total de arriba contaria los cerrados y
    una pagina de doce podria mostrar tres. Como EXISTS, el filtro entra en el
    WHERE: una sola consulta y un total que dice la verdad.

    Las tres ramas son las mismas de esta_abierto(): el rango normal de hoy, la
    primera mitad de un rango que cruza medianoche (abre hoy y cierra mañana) y
    la segunda mitad, que la aporta el horario de AYER.
    """
    hoy, ayer, momento = ventana_actual(ahora)

    rango_normal = and_(
        Horario.cierra > Horario.abre,
        Horario.abre <= momento,
        Horario.cierra > momento,
    )
    # Cruza medianoche: hoy cuenta desde que abre hasta las 23:59...
    cruza_hoy = and_(Horario.cierra < Horario.abre, Horario.abre <= momento)
    # ...y la madrugada de hoy la cubre el rango de ayer, hasta que cierra.
    cruza_ayer = and_(Horario.cierra < Horario.abre, Horario.cierra > momento)

    return (
        db.session.query(Horario.id)
        .filter(
            Horario.user_id == Post.author,
            # Un dia marcado cerrado, o sin horas cargadas, no abre nunca.
            Horario.cerrado.is_(False),
            Horario.abre.isnot(None),
            Horario.cierra.isnot(None),
            or_(
                and_(Horario.dia_semana == hoy, or_(rango_normal, cruza_hoy)),
                and_(Horario.dia_semana == ayer, cruza_ayer),
            ),
        )
        .exists()
    )


def _coincide_en_catalogo_sql(patron):
    """EXISTS que dan True si el texto buscado aparece en el catalogo del post.

    Uno por tabla -- products y services -- correlacionados con Post por
    post_id, igual que _abierto_ahora_sql se correlaciona por author.

    DOS EXISTS Y NO UN JOIN, que es lo que sale primero. Joineando products y
    services, un emprendimiento con cuatro productos que matchean vuelve
    cuatro veces: la grilla lo muestra repetido y, peor, paginacion.total lo
    cuenta cuatro. El EXISTS pregunta "hay alguno?" y corta ahi, asi que cada
    post sigue siendo una fila pase lo que pase. Lo mismo que ya se resolvio
    en metricas_de_posts, donde tres joins a la vez inflaban los COUNT.

    Las dos descripciones son nullable, y eso no necesita un chequeo aparte:
    un ILIKE contra NULL da NULL, que dentro de un OR no aporta nada y no
    descarta nada.

    SOLO LO DISPONIBLE. Un producto o un servicio apagado no se le muestra a
    nadie salvo al dueño (ver productos_de y servicios_de, que filtran igual
    para el que no es dueño), asi que tampoco puede hacer aparecer al
    emprendimiento en una busqueda: quien busca "alfajores" entraria a la
    panaderia para no encontrar ni un alfajor. El filtro va con .is_(True) y
    no con == True por el mismo motivo que Horario.cerrado.is_(False) unas
    lineas arriba; las dos columnas son NOT NULL con default True, asi que no
    hay tercer estado del que preocuparse.

    Esto NO esconde el emprendimiento: es una rama del OR. Si el post matchea
    por su titulo, por su cuerpo o por otro item que si esta disponible, sigue
    apareciendo igual.
    """
    en_productos = (
        db.session.query(Product.id)
        .filter(
            Product.post_id == Post.id,
            Product.disponible.is_(True),
            or_(Product.nombre.ilike(patron), Product.descripcion.ilike(patron)),
        )
        .exists()
    )
    en_servicios = (
        db.session.query(Service.id)
        .filter(
            Service.post_id == Post.id,
            Service.disponible.is_(True),
            or_(Service.titulo.ilike(patron), Service.descripcion.ilike(patron)),
        )
        .exists()
    )
    return or_(en_productos, en_servicios)


def buscar_posts(
    busqueda, categoria, lat, lon, pagina, por_pagina,
    con_resenias=False, radio_km=None, abierto_ahora=False,
):
    """El listado publico, ya paginado.

    Devuelve (paginacion, ordenado_por_distancia). Cuando ordena por distancia
    cada fila trae una columna extra con los km, asi que quien lo consume tiene
    que saber en cual de los dos modos vino; por eso el bool va en el retorno y
    no lo tiene que deducir la vista mirando lat y lon otra vez.

    con_resenias deja solo los que tienen al menos una. Lo resuelve la misma
    subquery que ya trae el promedio (ver services/ratings.py), no un join
    aparte.

    radio_km acota los resultados a esa distancia. Solo tiene efecto cuando hay
    lat/lon: sin coordenadas no hay desde donde medir, asi que se ignora en vez
    de vaciar el listado. Sin radio, el comportamiento es el mismo de siempre:
    ordena por cercania y no descarta nada por lejos que este.

    abierto_ahora deja solo los que estan atendiendo en este momento, segun
    los horarios del emprendedor y el reloj de Argentina. Lo resuelve un EXISTS
    sobre horarios (ver _abierto_ahora_sql), no un bucle sobre las filas.

    La busqueda por texto mira el titulo y el cuerpo del emprendimiento y
    tambien su catalogo disponible: el nombre y la descripcion de sus
    productos, y el titulo y la descripcion de sus servicios (ver
    _coincide_en_catalogo_sql). Alguien que busca "alfajores" encuentra la
    panaderia aunque la palabra no este en la descripcion del emprendimiento
    sino en un producto suyo, que es como la gente busca.

    La relacion author_user usa lazy="joined", asi que el autor viene en la
    misma consulta y no se dispara un SELECT por cada post (problema N+1). El
    promedio de reseñas se trae con el mismo criterio (ver services/ratings.py).
    """
    query = query_posts_con_rating(solo_con_resenias=con_resenias)

    if busqueda:
        patron = f"%{busqueda}%"
        # El catalogo es UNA RAMA MAS DEL OR, no un reemplazo: un post sin
        # productos ni servicios se sigue encontrando por su propio titulo o
        # cuerpo, exactamente como antes.
        query = query.filter(or_(
            Post.title.ilike(patron),
            Post.body.ilike(patron),
            _coincide_en_catalogo_sql(patron),
        ))

    if categoria:
        query = query.filter(Post.category == categoria)

    if abierto_ahora:
        query = query.filter(_abierto_ahora_sql())

    ordenar_por_distancia = lat is not None and lon is not None
    if ordenar_por_distancia:
        # Sin coordenadas propias, un post no tiene con que calcular la
        # distancia: se excluye en vez de mostrarlo con un orden arbitrario.
        query = query.filter(Post.latitude.isnot(None), Post.longitude.isnot(None))
        distancia = _distancia_km(lat, lon)
        query = query.add_columns(distancia.label("distance_km"))
        if radio_km is not None:
            # Va la expresion entera y no la etiqueta "distance_km": MySQL no
            # deja usar un alias del SELECT adentro del WHERE.
            query = query.filter(distancia <= radio_km)
        orden = distancia.asc()
    else:
        orden = Post.created.desc()

    paginacion = query.order_by(orden).paginate(
        page=pagina, per_page=por_pagina, error_out=False
    )
    return paginacion, ordenar_por_distancia


def conteo_por_categoria():
    """{categoria: cuantos}, para los numeros de la columna de filtros.

    Es una sola consulta agrupada y no siete COUNT: la columna los muestra
    todos juntos. Las categorias sin ningun emprendimiento no vuelven en el
    resultado, asi que quien lo use tiene que caer a 0 (el template lo hace con
    un `.get`), en vez de dejar el rubro afuera: la lista de rubros es fija y
    tiene que verse entera aunque alguno este vacio.
    """
    filas = db.session.query(Post.category, func.count(Post.id)).group_by(
        Post.category
    ).all()
    return {categoria: total for categoria, total in filas}


def posts_de(user_id, pagina, por_pagina):
    """Los emprendimientos de ese usuario, paginados."""
    return (
        Post.query.filter_by(author=user_id)
        .order_by(Post.created.desc())
        .paginate(page=pagina, per_page=por_pagina, error_out=False)
    )


def metricas_de_posts(post_ids):
    """{post_id: {resenias, promedio, productos, servicios}} para un listado.

    Las tres metricas que "Mis emprendimientos" muestra en cada fila salen de
    aca en UNA consulta para toda la pagina, y no una por post: pedirlas post
    por post en el bucle de la vista son cuatro consultas por fila (mismo
    problema N+1 que ya resuelven conteo_por_categoria y reputacion_de).

    Cada COUNT vive en su propia subconsulta agrupada y despues se outerjoinea
    por post_id, en vez de juntar los tres joins en una sola query: joineando
    reviews, products y services a la vez cada fila se multiplica contra las
    otras dos tablas (producto cartesiano) y los COUNT salen inflados. Ya
    agregadas, las subconsultas traen una fila por post y el join es 1 a 1.

    Un post sin reseñas, sin productos o sin servicios no aparece en la
    subconsulta correspondiente: el outerjoin lo deja en NULL y se cae a 0 (o a
    None en el promedio, mismo criterio que promedio_de_rating).
    """
    if not post_ids:
        # Sin esto seria un `IN ()`: una consulta que ya sabemos que no
        # devuelve nada. La pagina vacia del listado es un caso normal.
        return {}

    resenias = (
        db.session.query(
            Review.post_id.label("post_id"),
            func.count(Review.id).label("total"),
            func.avg(Review.rating).label("promedio"),
        )
        .filter(Review.post_id.in_(post_ids))
        .group_by(Review.post_id)
        .subquery()
    )
    productos = (
        db.session.query(
            Product.post_id.label("post_id"),
            func.count(Product.id).label("total"),
        )
        .filter(Product.post_id.in_(post_ids))
        .group_by(Product.post_id)
        .subquery()
    )
    servicios = (
        db.session.query(
            Service.post_id.label("post_id"),
            func.count(Service.id).label("total"),
        )
        .filter(Service.post_id.in_(post_ids))
        .group_by(Service.post_id)
        .subquery()
    )

    filas = (
        db.session.query(
            Post.id,
            resenias.c.total,
            resenias.c.promedio,
            productos.c.total,
            servicios.c.total,
        )
        .outerjoin(resenias, resenias.c.post_id == Post.id)
        .outerjoin(productos, productos.c.post_id == Post.id)
        .outerjoin(servicios, servicios.c.post_id == Post.id)
        .filter(Post.id.in_(post_ids))
        .all()
    )

    return {
        post_id: {
            "resenias": total_resenias or 0,
            "promedio": round(promedio, 1) if promedio else None,
            "productos": total_productos or 0,
            "servicios": total_servicios or 0,
        }
        for post_id, total_resenias, promedio, total_productos, total_servicios
        in filas
    }


def _orden_de_favoritos_sql(orden):
    """Las clausulas del ORDER BY de "Mis favoritos", segun lo que eligio el usuario.

    Aparte de favoritos_de() por lo mismo que _abierto_ahora_sql: es una
    decision con ramas propias, y adentro de la consulta obligaria a leer todo
    el armado para entender cual es el orden.

    NOMBRE ordena por lower(title) y no por title a secas: en SQLite un ORDER
    BY de texto es sensible a mayusculas y pone "Zapateria" antes que
    "alfajores", mientras que MySQL con su collation ci no. Sin el lower(), el
    "A-Z" que promete la etiqueta seria distinto en los tests que en
    produccion, y en produccion seria el unico correcto por accidente.

    Cualquier valor que no sea uno de los dos cae en RECIENTE, que es el
    default de la pantalla; validarlo es de reglas.orden_de_favoritos_valido y
    elegir el default es de la vista, asi que esto solo traduce.

    LOS DOS ORDENES TERMINAN EN Favorite.id.desc(), que es el desempate. Sin
    el, dos filas con la misma clave de orden quedan en el orden que quiera el
    motor, y no es un caso raro: en MySQL la columna es DATETIME(0), asi que
    todo lo que se marca dentro del mismo segundo empata (marcar varios
    favoritos seguidos es exactamente eso). Empatados, el resultado no solo es
    arbitrario sino inestable entre consultas, y con paginado eso se ve como
    una tarjeta repetida en dos paginas o una que no aparece en ninguna.
    Alcanza con el id porque es autoincremental: mayor id es favorito marcado
    despues, que es el mismo criterio que RECIENTE quiere. En SQLite no se
    nota porque guarda los microsegundos y casi nunca hay empate; la que
    importa es produccion.
    """
    if orden == reglas.OrdenesFavoritos.NOMBRE:
        # El desempate tambien aca: dos emprendimientos distintos pueden
        # llamarse igual, y ahi el A-Z solo no alcanza para fijar el orden.
        return (func.lower(Post.title).asc(), Favorite.id.desc())
    # POR CUANDO SE MARCO EL FAVORITO, no por cuando se publico el
    # emprendimiento (Post.created, que es lo que ordenaba antes). Son cosas
    # distintas y la que importa aca es la marca: alguien que acaba de guardar
    # una panaderia de 2024 la quiere ver arriba, y con el orden viejo aparecia
    # sepultada bajo todo lo que se publico despues.
    return (Favorite.created.desc(), Favorite.id.desc())


def favoritos_de(user_id, pagina, por_pagina, categoria=None, orden=None):
    """Los emprendimientos que ese usuario marco como favoritos, paginados.

    categoria acota a un rubro. Mismo trato que en buscar_posts: se espera ya
    validada (None es "todos"), porque quien sabe que hacer con una categoria
    que no existe es la vista, que ademas tiene que repintar el <select>.

    orden elige entre los de reglas.OrdenesFavoritos; ver
    _orden_de_favoritos_sql para el criterio de cada uno y para el default.
    """
    consulta = (
        query_posts_con_rating(Post.query.join(Favorite, Favorite.post_id == Post.id))
        .filter(Favorite.user_id == user_id)
    )

    if categoria:
        consulta = consulta.filter(Post.category == categoria)

    return consulta.order_by(*_orden_de_favoritos_sql(orden)).paginate(
        page=pagina, per_page=por_pagina, error_out=False
    )


def productos_de(post_id, solo_disponibles):
    """El catalogo del emprendimiento.

    solo_disponibles lo decide la vista segun quien mira: los productos
    apagados los ve solo el dueño. El filtro va en la consulta y no en el
    template porque filtrando al mostrar los datos igual viajarian al HTML y
    cualquiera los leeria en el codigo fuente.
    """
    consulta = Product.query.filter_by(post_id=post_id)
    if solo_disponibles:
        consulta = consulta.filter_by(disponible=True)
    return consulta.order_by(Product.nombre).all()


def servicios_de(post_id, solo_disponibles):
    """Los servicios del emprendimiento, con el mismo criterio que el catalogo."""
    consulta = Service.query.filter_by(post_id=post_id)
    if solo_disponibles:
        consulta = consulta.filter_by(disponible=True)
    return consulta.order_by(Service.titulo).all()


def resenias_de(post_id):
    return (
        Review.query
        .filter_by(post_id=post_id)
        .order_by(Review.created.desc())
        .all()
    )


def promedio_de_rating(post_id):
    """El promedio de estrellas, redondeado a un decimal, o None si no hay."""
    promedio = (
        db.session.query(func.avg(Review.rating))
        .filter(Review.post_id == post_id)
        .scalar()
    )
    return round(promedio, 1) if promedio else None


def resenia_de(post_id, user_id):
    """La resenia que ese usuario dejo en ese post, si dejo alguna."""
    return Review.query.filter_by(post_id=post_id, user_id=user_id).first()


def favorito_de(user_id, post_id):
    return Favorite.query.filter_by(user_id=user_id, post_id=post_id).first()


def hay_reporte_pendiente(reporter_id, tipo, target_id):
    """Si ese usuario ya tiene un reporte sin resolver sobre ese objetivo.

    No tiene sentido dejar que el mismo usuario apile reportes sobre el mismo
    objetivo: uno sin resolver ya alcanza para que el admin lo vea.

    NO ES LA GARANTIA. Entre este SELECT y el INSERT queda una ventana, y dos
    POST simultaneos (el doble click, dos pestañas) pasarian los dos. Lo que de
    verdad lo impide es el UNIQUE (reporter_id, clave_pendiente) de la base;
    esta consulta esta para pintar el formulario y dar un mensaje claro antes
    de llegar a chocar. El por que de la columna centinela, en modelo_reporte.py.
    """
    filtro_objetivo = (
        {"post_id": target_id} if tipo == "post" else {"review_id": target_id}
    )
    return Report.query.filter_by(
        reporter_id=reporter_id, resolved=False, **filtro_objetivo
    ).first() is not None


def tiene_horarios_cargados(user_id):
    """Si ese usuario ya cargo sus horarios de atencion.

    Un EXISTS y no traer las filas: lo unico que se pregunta es si hay alguna,
    para el item del checklist de publicacion. Los horarios cuelgan del USUARIO
    y no del emprendimiento (ver app/perfil/modelo_horario.py), asi que el
    item ya puede estar cumplido cuando se publica el primer emprendimiento.
    """
    return db.session.query(
        Horario.query.filter(Horario.user_id == user_id).exists()
    ).scalar()


def reordenar_fotos(post, tokens):
    """Aplica el orden nuevo de las fotos, incluida cual pasa a ser la principal.

    `tokens` ya viene validado (ver reglas.orden_de_fotos_valido): es una
    permutacion exacta de las fotos del post. El primero es la principal.

    NO se toca ningun archivo del disco ni se crea ninguna fila: las filas de
    post_images que ya existen se quedan y lo unico que cambia es a que archivo
    apunta cada una. Mover la principal a la galeria (o al reves) es entonces
    intercambiar dos strings, no mover un archivo de una carpeta a otra ni
    borrar y volver a subir. Un archivo perdido no se recupera; un `filename`
    reasignado si.

    El unico caso con filas de mas es un post SIN principal (Post.image en
    NULL) que promueve una de la galeria: ahi el total de fotos no cambia pero
    una pasa a vivir en Post.image, asi que sobra exactamente una fila de
    post_images y se borra. Su archivo no se toca: lo referencia Post.image
    desde ese momento.
    """
    por_token = {str(imagen.id): imagen for imagen in post.imagenes}
    nombres = [
        post.image if token == reglas.TOKEN_PRINCIPAL else por_token[token].filename
        for token in tokens
    ]

    principal, resto = nombres[0], nombres[1:]
    filas = list(post.imagenes)
    # Nunca puede faltar fila: `resto` tiene a lo sumo tantos elementos como
    # filas hay (una foto mas que filas solo existe si hay principal, y esa se
    # va en `principal`). Si esto no se cumpliera estariamos por perder una
    # foto en silencio.
    assert len(resto) <= len(filas)

    for posicion, (fila, nombre) in enumerate(zip(filas, resto)):
        fila.filename = nombre
        fila.posicion = posicion

    for sobrante in filas[len(resto):]:
        db.session.delete(sobrante)

    post.image = principal
    db.session.commit()


def guardar(fila=None):
    """Confirma la transaccion, agregando la fila nueva si se pasa una.

    Existe para que las vistas no importen db solo para escribir dos lineas de
    sesion; el manejo del IntegrityError se queda arriba, que es donde se sabe
    que significa el choque.
    """
    if fila is not None:
        db.session.add(fila)
    db.session.commit()


def sumar_una_vista(post):
    """Suma uno al contador de vistas del post, en la base y no en Python.

    Se hace con un UPDATE (views_count = views_count + 1) y no con el
    read-modify-write que habia antes (post.views_count += 1 y commit): con dos
    visitas al mismo emprendimiento a la vez, los dos procesos leian el mismo
    numero, los dos escribian ese numero mas uno, y una de las dos vistas se
    perdia. Con la suma adentro del UPDATE la hace el motor sobre la fila
    bloqueada, asi que las dos cuentan.

    Despues del UPDATE se expira el atributo en vez de refrescarlo: el objeto
    de la sesion todavia tiene el valor viejo, y expirarlo hace que se relea
    solo si alguien lo mira -- que en el detalle no pasa, porque el contador es
    dato del dueño y del dueño no se cuentan las vistas.
    """
    Post.query.filter_by(id=post.id).update(
        {Post.views_count: Post.views_count + 1}, synchronize_session=False
    )
    db.session.commit()
    db.session.expire(post, ["views_count"])


def borrar(fila):
    db.session.delete(fila)
    db.session.commit()


def descartar():
    db.session.rollback()
