"""Helper para traer emprendimientos junto con su promedio de reseñas.

Antes esta misma consulta (outerjoin a una subquery agrupada por post) estaba
duplicada en blog.index() y en profile.py. Pedirla post por post en un bucle
dispara una consulta extra por cada tarjeta (problema N+1); centralizarla
ademas evita que las tres copias se desincronicen si cambia la logica.
"""

from sqlalchemy import func

from db import db
from app.blog.modelo_post import Post
from app.blog.modelo_resenia import Review


def query_posts_con_rating(query=None, solo_con_resenias=False):
    """Devuelve una Query de Post que trae (Post, avg_rating, review_count) por fila.

    solo_con_resenias deja afuera a los que no tienen ninguna. Se resuelve
    sobre ESTA misma subquery en vez de agregar un EXISTS o un segundo join: la
    agregacion por post ya esta calculada aca, asi que pedirle que la fila
    exista (post_id no nulo) convierte el outerjoin en un inner join sin sumar
    otra pasada por reviews.

    El filtro vive en este helper y no afuera justamente porque `ratings` es
    local: sin esto, quien quisiera filtrar por reseñas tendria que rearmar la
    subquery por su cuenta y terminariamos con dos agregaciones que se pueden
    desincronizar.
    """
    if query is None:
        query = Post.query

    ratings = (
        db.session.query(
            Review.post_id.label("post_id"),
            func.avg(Review.rating).label("avg_rating"),
            func.count(Review.id).label("review_count"),
        )
        .group_by(Review.post_id)
        .subquery()
    )
    query = (
        query
        .outerjoin(ratings, ratings.c.post_id == Post.id)
        .add_columns(ratings.c.avg_rating, ratings.c.review_count)
    )

    if solo_con_resenias:
        # Se mira post_id y no review_count > 0: el COUNT de un grupo nunca da
        # cero (un post sin reseñas no arma grupo), asi que lo que distingue es
        # si el outerjoin encontro fila o la dejo en NULL.
        query = query.filter(ratings.c.post_id.isnot(None))

    return query


def serializar_con_rating(filas, favoritos=frozenset()):
    """Convierte filas (Post, avg_rating, review_count) en dicts listos para el template."""
    return [
        {
            "post": post,
            "avg_rating": round(avg_rating, 1) if avg_rating else None,
            "review_count": review_count or 0,
            "is_favorite": post.id in favoritos,
        }
        for post, avg_rating, review_count in filas
    ]
