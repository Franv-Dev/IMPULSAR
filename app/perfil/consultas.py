"""Todo lo que este dominio le pregunta a la base.

Es la unica capa que arma querys. Las vistas no tocan db.session: piden por
nombre lo que necesitan.

Las metricas del dueño (estadisticas_de_usuario) estaban en services/stats.py.
Se mudan aca sin tocarles una linea: no son un servicio compartido, las usa solo
el perfil, y en services/ estaban por la razon con la que sube todo a services/
hoy, que es que en su momento la consulta molesto en dos lugares.

Los joinedload no son un detalle de performance suelto: sin ellos, pintar el
perfil dispara un SELECT por evento y por reseña para ir a buscar el
emprendimiento (el problema N+1). Van en la consulta y no en la vista para que
no se pierdan cuando alguien reescriba la vista.
"""

from sqlalchemy import func
from sqlalchemy.orm import joinedload

from app.perfil.modelo_follow import Follow
from db import db
from models.event import Event
from models.favorite import Favorite
from models.post import Post
from models.review import Review
from models.user import User
from services.eventos import eventos_de_usuario, pasados, proximos
from services.ratings import query_posts_con_rating


def usuario_por_slug_o_404(slug):
    return User.query.filter_by(slug=slug).first_or_404()


def usuario_por_id_o_404(user_id):
    return User.query.get_or_404(user_id)


def emprendimientos_con_rating_de(user_id):
    """Los emprendimientos del usuario, cada uno con su promedio de reseñas."""
    return (
        query_posts_con_rating(Post.query.filter_by(author=user_id))
        .order_by(Post.created.desc())
        .all()
    )


def horarios_de(user):
    """Los horarios del usuario ordenados por dia, de lunes a domingo."""
    return sorted(user.horarios, key=lambda h: h.dia_semana)


def horarios_por_dia_de(user):
    """Los mismos horarios pero indexados por dia, para el panel de edicion."""
    return {h.dia_semana: h for h in user.horarios}


def seguimiento_entre(follower_id, followed_id):
    """La fila de seguimiento, si ese usuario sigue al otro."""
    return Follow.query.filter_by(
        follower_id=follower_id, followed_id=followed_id
    ).first()


def a_quienes_sigue(user_id):
    return (
        User.query.join(Follow, Follow.followed_id == User.id)
        .filter(Follow.follower_id == user_id)
        .order_by(Follow.created.desc())
        .all()
    )


def eventos_del_perfil(user_id, maximo_pasados):
    """Los eventos publicados por ese usuario: (proximos, pasados).

    Los pasados van acotados: un historial completo no aporta y alarga el
    perfil.
    """
    consulta = eventos_de_usuario(user_id).options(joinedload(Event.post))
    return proximos(consulta).all(), pasados(consulta).limit(maximo_pasados).all()


def resenias_recibidas_por(user_id, page, per_page):
    """Las reseñas de TODOS los emprendimientos del usuario, paginadas.

    A diferencia del detalle de un post (que solo muestra las de ESE
    emprendimiento), esto las junta en un solo listado.
    """
    return (
        Review.query
        .join(Post, Post.id == Review.post_id)
        .options(joinedload(Review.post), joinedload(Review.user))
        .filter(Post.author == user_id)
        .order_by(Review.created.desc())
        .paginate(page=page, per_page=per_page, error_out=False)
    )


def estadisticas_de_usuario(user_id):
    """Las metricas acumuladas de todos los emprendimientos del usuario.

    Son datos privados del dueño del perfil, igual que views_count en un post:
    no se calculan ni se pasan al template cuando quien mira es otro usuario, y
    no se agregan a User.serialize() para que no viajen por la API publica.

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


def agregar(fila):
    """Suma la fila a la sesion sin confirmar todavia.

    La usa el panel de horarios, que arma hasta siete filas y las guarda todas
    juntas en un solo commit.
    """
    db.session.add(fila)


def guardar(fila=None):
    """Confirma la transaccion, agregando la fila nueva si se pasa una."""
    if fila is not None:
        db.session.add(fila)
    db.session.commit()


def borrar(fila):
    db.session.delete(fila)
    db.session.commit()


def descartar():
    db.session.rollback()
