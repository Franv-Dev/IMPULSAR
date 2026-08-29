"""Todo lo que este dominio le pregunta a la base.

Es la unica capa que arma querys. Las vistas no tocan db.session: piden por
nombre lo que necesitan, y si mañana una consulta necesita otro joinedload u
otro orden, se cambia aca sin abrir ninguna ruta.

El listado publico es el caso mas grande: filtros por texto, por categoria y por
cercania, mas la paginacion. Se arma entero aca y la vista recibe la pagina ya
resuelta, porque cada uno de esos filtros es una decision sobre la consulta, no
sobre la pantalla.
"""

from sqlalchemy import case, func

from app.blog.modelo_favorito import Favorite
from app.blog.modelo_post import Post
from app.blog.modelo_reporte import Report
from app.blog.modelo_resenia import Review
from app.perfil.modelo_horario import Horario
from app.servicios.modelo import Service
from db import db
from models.product import Product
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


def buscar_posts(
    busqueda, categoria, lat, lon, pagina, por_pagina,
    con_resenias=False, radio_km=None,
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

    La relacion author_user usa lazy="joined", asi que el autor viene en la
    misma consulta y no se dispara un SELECT por cada post (problema N+1). El
    promedio de reseñas se trae con el mismo criterio (ver services/ratings.py).
    """
    query = query_posts_con_rating(solo_con_resenias=con_resenias)

    if busqueda:
        patron = f"%{busqueda}%"
        query = query.filter(Post.title.ilike(patron) | Post.body.ilike(patron))

    if categoria:
        query = query.filter(Post.category == categoria)

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


def favoritos_de(user_id, pagina, por_pagina):
    """Los emprendimientos que ese usuario marco como favoritos, paginados."""
    return (
        query_posts_con_rating(Post.query.join(Favorite, Favorite.post_id == Post.id))
        .filter(Favorite.user_id == user_id)
        .order_by(Post.created.desc())
        .paginate(page=pagina, per_page=por_pagina, error_out=False)
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


def guardar(fila=None):
    """Confirma la transaccion, agregando la fila nueva si se pasa una.

    Existe para que las vistas no importen db solo para escribir dos lineas de
    sesion; el manejo del IntegrityError se queda arriba, que es donde se sabe
    que significa el choque.
    """
    if fila is not None:
        db.session.add(fila)
    db.session.commit()


def borrar(fila):
    db.session.delete(fila)
    db.session.commit()


def descartar():
    db.session.rollback()
