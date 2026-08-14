"""Helper para traer emprendimientos junto con su promedio de reseñas.

Antes esta misma consulta (outerjoin a una subquery agrupada por post) estaba
duplicada en blog.index() y en profile.py. Pedirla post por post en un bucle
dispara una consulta extra por cada tarjeta (problema N+1); centralizarla
ademas evita que las tres copias se desincronicen si cambia la logica.
"""

from sqlalchemy import func

from db import db
from models.post import Post
from models.review import Review


def query_posts_con_rating(query=None):
    """Devuelve una Query de Post que trae (Post, avg_rating, review_count) por fila."""
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
    return (
        query
        .outerjoin(ratings, ratings.c.post_id == Post.id)
        .add_columns(ratings.c.avg_rating, ratings.c.review_count)
    )


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
