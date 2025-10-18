from flask import Blueprint, jsonify
from models.post import Post
from sqlalchemy.exc import SQLAlchemyError

posts_api = Blueprint("posts_api", __name__, url_prefix="/api/posts")


# ===============================
#   LISTAR PUBLICACIONES
# ===============================
@posts_api.get("/")
def list_posts():
    try:
        posts = Post.query.order_by(Post.created.desc()).all()
        if not posts:
            return jsonify({"message": "No hay publicaciones disponibles"}), 200

        return jsonify({
            "message": "Publicaciones obtenidas correctamente",
            "posts": [p.serialize() for p in posts]
        }), 200

    except SQLAlchemyError as e:
        return jsonify({"error": "Error al obtener las publicaciones", "details": str(e)}), 500


# ===============================
#   OBTENER PUBLICACIÓN POR ID
# ===============================
@posts_api.get("/<int:post_id>")
def get_post(post_id):
    try:
        post = Post.query.get(post_id)
        if not post:
            return jsonify({"error": f"No existe publicación con id {post_id}"}), 404

        return jsonify({
            "message": "Publicación obtenida correctamente",
            "post": post.serialize()
        }), 200

    except SQLAlchemyError as e:
        return jsonify({"error": "Error al obtener la publicación", "details": str(e)}), 500
