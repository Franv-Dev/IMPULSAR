from flask import Blueprint, current_app, g, jsonify, request

from app.blog import consultas
from app.blog.modelo_post import Categorias, Post

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

    query = Post.query
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
            _con_favorito(p, favoritos) for p in paginacion.items
        ],
        "page": paginacion.page,
        "per_page": paginacion.per_page,
        "pages": paginacion.pages,
        "total": paginacion.total,
        "has_next": paginacion.has_next,
        "has_prev": paginacion.has_prev,
    }), 200


def _con_favorito(post, favoritos):
    """El post serializado, con el favorito del usuario si hay sesion.

    La clave no viaja cuando nadie esta logueado, en vez de viajar en False:
    "no lo tenes en favoritos" y "no sabemos quien sos" no son lo mismo, y el
    que consume tiene que poder distinguirlos para decidir si dibuja el corazon.
    """
    datos = post.to_dict(include_views=bool(g.user and g.user.id == post.author))
    if g.user:
        datos["favorito"] = post.id in favoritos
    return datos


@posts_api.get("/<int:post_id>")
def get_post(post_id):
    post = Post.query.get_or_404(post_id)
    include_views = bool(g.user and g.user.id == post.author)
    return jsonify(post.to_dict(include_views=include_views)), 200
