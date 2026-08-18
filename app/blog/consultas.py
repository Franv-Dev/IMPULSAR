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


def buscar_posts(busqueda, categoria, lat, lon, pagina, por_pagina):
    """El listado publico, ya paginado.

    Devuelve (paginacion, ordenado_por_distancia). Cuando ordena por distancia
    cada fila trae una columna extra con los km, asi que quien lo consume tiene
    que saber en cual de los dos modos vino; por eso el bool va en el retorno y
    no lo tiene que deducir la vista mirando lat y lon otra vez.

    La relacion author_user usa lazy="joined", asi que el autor viene en la
    misma consulta y no se dispara un SELECT por cada post (problema N+1). El
    promedio de reseñas se trae con el mismo criterio (ver services/ratings.py).
    """
    query = query_posts_con_rating()

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
        orden = distancia.asc()
    else:
        orden = Post.created.desc()

    paginacion = query.order_by(orden).paginate(
        page=pagina, per_page=por_pagina, error_out=False
    )
    return paginacion, ordenar_por_distancia


def posts_de(user_id, pagina, por_pagina):
    """Los emprendimientos de ese usuario, paginados."""
    return (
        Post.query.filter_by(author=user_id)
        .order_by(Post.created.desc())
        .paginate(page=pagina, per_page=por_pagina, error_out=False)
    )


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
