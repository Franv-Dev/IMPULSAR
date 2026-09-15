from flask import Blueprint, abort, current_app, g, jsonify, request

from app.blog import consultas, reglas
from app.blog.modelo_post import Categorias, Post
from services.ratings import query_posts_con_rating

posts_api = Blueprint("posts_api", __name__, url_prefix="/api/posts")

# Tope duro de resultados por pagina: sin esto alguien pide ?per_page=999999
# y se lleva la base entera en una sola consulta.
MAX_POR_PAGINA = 50


@posts_api.get("/")
def list_posts():
    """Listado paginado de emprendimientos, con busqueda opcional.

    Parametros de query:
        page     numero de pagina (por defecto 1)
        per_page resultados por pagina (tope MAX_POR_PAGINA)
        q        texto a buscar en el titulo y la descripcion
    """
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get(
        "per_page", current_app.config["POSTS_POR_PAGINA"], type=int
    )
    per_page = max(1, min(per_page, MAX_POR_PAGINA))

    # El promedio de reseñas viaja en cada fila porque la tarjeta del inicio lo
    # muestra, igual que la del listado. Sale del mismo helper que usa /blog/
    # (una subquery agrupada con outerjoin), no de un promedio por tarjeta:
    # pedirlo post por post seria una consulta por fila. Cada fila pasa a ser
    # la tupla (Post, avg_rating, review_count).
    # Sin borradores: esta API es publica y sin sesion, asi que es la forma mas
    # facil de leer un emprendimiento que su dueño todavia no publico.
    query = reglas.solo_publicados(query_posts_con_rating())
    busqueda = (request.args.get("q") or "").strip()
    if busqueda:
        # La busqueda pasa a resolverse en la base de datos. Antes se traian
        # todos los posts al navegador y se filtraban ahi, lo que no escala.
        patron = f"%{busqueda}%"
        query = query.filter(Post.title.ilike(patron) | Post.body.ilike(patron))

    categoria = (request.args.get("category") or "").strip()
    if categoria in Categorias.TODAS:
        query = query.filter(Post.category == categoria)

    paginacion = (
        query.order_by(Post.created.desc())
        .paginate(page=page, per_page=per_page, error_out=False)
    )

    # Que esta en favoritos lo dice esta API porque la home pinta sus tarjetas
    # con JavaScript y no tiene otro lado de donde sacarlo. Es UNA consulta
    # para toda la pagina (ids_favoritos ya devuelve el set entero), no una por
    # tarjeta, y sale solo si hay sesion: para quien mira sin loguearse la
    # respuesta es la de siempre.
    favoritos = consultas.ids_favoritos(g.user.id) if g.user else frozenset()

    return jsonify({
        "items": [
            _serializar(fila, favoritos) for fila in paginacion.items
        ],
        "page": paginacion.page,
        "per_page": paginacion.per_page,
        "pages": paginacion.pages,
        "total": paginacion.total,
        "has_next": paginacion.has_next,
        "has_prev": paginacion.has_prev,
    }), 200


def _serializar(fila, favoritos):
    """Una fila (Post, avg_rating, review_count) lista para la tarjeta del inicio.

    Sobre el post serializado se agregan tres cosas que el JSON base no trae
    porque no son columnas de Post:

    - `favorito`, que NO viaja cuando nadie esta logueado en vez de viajar en
      False: "no lo tenes en favoritos" y "no sabemos quien sos" no son lo
      mismo, y el que consume tiene que poder distinguirlos para decidir si
      dibuja el corazon.
    - `avg_rating` y `review_count`, redondeados igual que en el listado
      (services/ratings.serializar_con_rating), asi la misma tarjeta muestra el
      mismo numero en las dos pantallas. Sin reseñas el promedio va en None y
      no en 0: un emprendimiento nuevo no esta calificado con un cero.
    - `author_name`, para el pie de la tarjeta. La relacion author_user es
      lazy="joined", asi que el autor ya viene con el post y esto no suma
      consultas.
    """
    post, avg_rating, review_count = fila

    datos = post.to_dict(include_views=bool(g.user and g.user.id == post.author))
    if g.user:
        datos["favorito"] = post.id in favoritos

    # float() y no el round() pelado: en MySQL el AVG vuelve como Decimal, que
    # jsonify serializa como cadena ("5.0"). El que consume esto es JavaScript
    # y espera un numero.
    datos["avg_rating"] = round(float(avg_rating), 1) if avg_rating else None
    datos["review_count"] = review_count or 0
    datos["author_name"] = post.author_user.username if post.author_user else None
    return datos


@posts_api.get("/<int:post_id>")
def get_post(post_id):
    post = Post.query.get_or_404(post_id)
    es_el_dueno = bool(g.user and reglas.es_el_autor(post, g.user.id))
    # Un borrador solo existe para su dueño. 404 y no 403 por lo mismo que la
    # ficha: un 403 confirmaria que ese id existe y esta sin publicar, que es
    # justamente lo que el dueño todavia no quiso contar.
    if post.es_borrador and not es_el_dueno:
        abort(404)
    return jsonify(post.to_dict(include_views=es_el_dueno)), 200
