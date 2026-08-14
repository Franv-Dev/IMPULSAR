"""Metricas agregadas de un emprendedor (vistas, favoritos, calificacion).

Son datos privados del dueño del perfil, igual que views_count en un post:
no se calculan ni se pasan al template cuando quien mira es otro usuario, y
no se agregan a User.serialize() para que no viajen por la API publica.
"""

from sqlalchemy import func

from db import db
from models.favorite import Favorite
from models.follow import Follow
from models.post import Post
from models.review import Review


def estadisticas_de_usuario(user_id):
    """Devuelve las metricas acumuladas de todos los emprendimientos del usuario.

    Son tres agregaciones separadas y no un solo join: cruzar favoritos y
    reseñas en la misma consulta multiplica las filas entre si (un post con 2
    favoritos y 3 reseñas daria 6), y con eso tanto la suma de vistas como el
    promedio quedarian inflados.
    """
    vistas = db.session.query(
        func.coalesce(func.sum(Post.views_count), 0)
    ).filter(Post.author == user_id).scalar()

    favoritos = (
        db.session.query(func.count(Favorite.id))
        .join(Post, Post.id == Favorite.post_id)
        .filter(Post.author == user_id)
        .scalar()
    )

    promedio, total_resenias = (
        db.session.query(func.avg(Review.rating), func.count(Review.id))
        .join(Post, Post.id == Review.post_id)
        .filter(Post.author == user_id)
        .one()
    )

    # La cantidad de seguidores va aca y no en la parte publica del perfil, por
    # el mismo criterio que las vistas: es una metrica del dueño. Quien lo
    # sigue no se expone en ningun lado.
    seguidores = (
        db.session.query(func.count(Follow.id))
        .filter(Follow.followed_id == user_id)
        .scalar()
    )

    return {
        "vistas": vistas or 0,
        "favoritos": favoritos or 0,
        "seguidores": seguidores or 0,
        # None (y no 0) cuando todavia no hay ninguna reseña: un promedio de
        # 0.0 se leeria como "lo calificaron pésimo".
        "promedio": round(promedio, 1) if promedio else None,
        "resenias": total_resenias or 0,
    }
