"""Saca de la base y del disco lo que dejo una corrida anterior."""

import os

from db import db
from models.message import Message
from models.product import Product
from models.user import User
from app.blog.modelo_favorito import Favorite
from app.blog.modelo_imagen import PostImage
from app.blog.modelo_post import Post
from app.blog.modelo_reporte import Report
from app.blog.modelo_resenia import Review
from app.perfil.modelo_follow import Follow
from app.servicios.modelo import Service
from app.servicios.modelo_solicitud import ServiceRequest

from scripts.seed.datos import EMAIL_SEED
from scripts.seed.imagenes import _carpeta_uploads


def _usuarios_de_seed():
    return User.query.filter(User.email.like(f"%{EMAIL_SEED}")).all()


def _archivos_de(ids_posts, ids_usuarios=()):
    """Los nombres de archivo que referencian las filas que borra borrar().

    Se pregunta a la base en vez de barrer el directorio buscando el prefijo:
    static/uploads es una sola carpeta para todas las bases, asi que un glob
    de seed_* se lleva tambien las imagenes de otra base sembrada aparte. Los
    nombres salen de las cuatro columnas que guardan uno: Post.image,
    PostImage.filename, Product.foto y ServiceRequest.foto.

    La foto de una solicitud es el unico caso que no cuelga de un post: borrar()
    se lleva tambien las solicitudes que un usuario del seed hizo sobre un
    servicio real, y esas cuelgan de un post ajeno. Por eso ademas de los posts
    recibe los usuarios, con el mismo criterio con el que se borran las filas:
    si el criterio de los dos lados no coincide, la fila se va y el archivo
    queda huerfano en el disco para siempre.
    """
    nombres = []

    if ids_posts:
        for post in Post.query.filter(Post.id.in_(ids_posts)):
            nombres.append(post.image)
        for (nombre,) in db.session.query(PostImage.filename).filter(
            PostImage.post_id.in_(ids_posts)
        ):
            nombres.append(nombre)
        for (nombre,) in db.session.query(Product.foto).filter(
            Product.post_id.in_(ids_posts)
        ):
            nombres.append(nombre)

    condiciones = []
    if ids_posts:
        condiciones.append(ServiceRequest.service_id.in_(
            db.session.query(Service.id).filter(Service.post_id.in_(ids_posts))
        ))
    if ids_usuarios:
        condiciones.append(ServiceRequest.cliente_id.in_(ids_usuarios))
    if condiciones:
        for (nombre,) in db.session.query(ServiceRequest.foto).filter(
            db.or_(*condiciones)
        ):
            nombres.append(nombre)

    return [n for n in nombres if n]


def _borrar_archivos(app, nombres):
    """Borra esos archivos del disco. Solo esos, por nombre exacto."""
    carpeta = _carpeta_uploads(app)
    borradas = 0
    for nombre in nombres:
        try:
            os.remove(os.path.join(carpeta, nombre))
            borradas += 1
        except FileNotFoundError:
            # Ya no estaba: nada que hacer, y no es un error.
            pass
        except OSError:
            print(f"  (no se pudo borrar {nombre})")
    return borradas


def borrar(app):
    """Saca todo lo que dejo este script, y nada mas.

    El orden es a mano y no por cascada, pero ya no porque haga falta: desde
    b2b97d078fb2 y c1f4a90b6e35 todas las FK a users y a posts tienen ON DELETE
    CASCADE, asi que borrar los usuarios de seed arrastraria esto solo, tanto
    lo que dejaron ellos como lo que usuarios REALES dejaron sobre contenido
    del seed (eso ultimo se va por la cascada del post, no la del usuario).

    Se mantiene explicito igual por una sola razon, que sigue en pie: este
    script tiene que decir exactamente que toca. Es la unica forma de revisar,
    leyendolo, que no se lleve nada de un usuario real que no sea su actividad
    sobre el seed. Una cascada hace lo mismo sin dejarlo escrito en ningun
    lado.
    """
    usuarios = _usuarios_de_seed()
    if not usuarios:
        print("No hay datos de seed que borrar.")
        # Y por lo tanto tampoco hay archivos: los nombres salen de las filas.
        print("Ningún archivo tocado.")
        return

    ids = [u.id for u in usuarios]
    posts = Post.query.filter(Post.author.in_(ids)).all()
    ids_posts = [p.id for p in posts]

    # Los nombres de archivo se juntan ANTES de borrar las filas: despues no
    # queda de donde sacarlos.
    archivos = _archivos_de(ids_posts, ids)

    def borrar_filas(modelo, condicion):
        modelo.query.filter(condicion).delete(synchronize_session=False)

    # Las solicitudes van primero porque cuelgan de services, que cuelga de
    # posts: si se borrara el post antes, la cascada del ORM ya se las habria
    # llevado y este filtro no encontraria las del usuario real.
    ids_servicios = [
        fila[0] for fila in db.session.query(Service.id).filter(
            Service.post_id.in_(ids_posts or [0])
        )
    ]
    borrar_filas(ServiceRequest, db.or_(
        ServiceRequest.cliente_id.in_(ids),
        ServiceRequest.service_id.in_(ids_servicios or [0]),
    ))

    borrar_filas(Report, db.or_(
        Report.reporter_id.in_(ids),
        Report.post_id.in_(ids_posts or [0]),
    ))
    borrar_filas(Follow, db.or_(
        Follow.follower_id.in_(ids), Follow.followed_id.in_(ids)
    ))
    borrar_filas(Favorite, db.or_(
        Favorite.user_id.in_(ids), Favorite.post_id.in_(ids_posts or [0])
    ))
    borrar_filas(Message, db.or_(
        Message.client_id.in_(ids), Message.sender_id.in_(ids),
        Message.post_id.in_(ids_posts or [0]),
    ))
    borrar_filas(Review, db.or_(
        Review.user_id.in_(ids), Review.post_id.in_(ids_posts or [0])
    ))
    db.session.flush()

    for post in posts:
        # Por el ORM y no con delete() masivo, para que se lleve productos,
        # eventos e imagenes con la cascada del modelo.
        db.session.delete(post)
    db.session.flush()

    for usuario in usuarios:
        db.session.delete(usuario)
    db.session.commit()
    print(f"Borrados {len(usuarios)} usuarios de seed y sus {len(posts)} emprendimientos.")

    borradas = _borrar_archivos(app, archivos)
    print(f"Borradas {borradas} imágenes del disco (de {len(archivos)} que referenciaban).")
