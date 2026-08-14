from flask import Blueprint, current_app, jsonify, request

from models.post import Categorias, Post

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

    return jsonify({
        "items": [p.to_dict() for p in paginacion.items],
        "page": paginacion.page,
        "per_page": paginacion.per_page,
        "pages": paginacion.pages,
        "total": paginacion.total,
        "has_next": paginacion.has_next,
        "has_prev": paginacion.has_prev,
    }), 200


@posts_api.get("/<int:post_id>")
def get_post(post_id):
    post = Post.query.get_or_404(post_id)
    return jsonify(post.to_dict()), 200
