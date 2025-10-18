from flask import Blueprint, request, jsonify, current_app
from werkzeug.exceptions import abort
from models.post import Post
from models.user import User
from views.auth import login_required
from db import db
from werkzeug.utils import secure_filename
from flask_jwt_extended import get_jwt_identity
import os

blog = Blueprint('blog', __name__, url_prefix='/blog')

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# Obtener usuario por ID
def get_user(id):
    user = User.query.get_or_404(id)
    return user


# ===============================
#   LISTAR PUBLICACIONES
# ===============================
@blog.route("/", methods=["GET"])
def index():
    posts = Post.query.all()
    posts = list(reversed(posts))
    return jsonify([p.serialize() for p in posts]), 200


# ===============================
#   CREAR PUBLICACIÓN
# ===============================
@blog.route("/create", methods=["POST"])
@login_required
def create():
    identity = get_jwt_identity()
    user_id = identity.get("id") if identity else None

    if not user_id:
        return jsonify({"error": "Usuario no autenticado"}), 401

    title = request.form.get("title")
    body = request.form.get("body")
    file = request.files.get("image")

    error = None
    filename = None

    if not title:
        error = "Se requiere un título"

    if file and file.filename != "":
        if allowed_file(file.filename):
            filename = secure_filename(file.filename)
            upload_path = os.path.join(current_app.root_path, 'static/uploads', filename)
            file.save(upload_path)
        else:
            error = "Formato de imagen no permitido (usa png, jpg, jpeg o gif)"

    if error:
        return jsonify({"error": error}), 400

    post = Post(user_id, title, body, filename)
    db.session.add(post)
    db.session.commit()

    return jsonify({
        "message": "Publicación creada correctamente",
        "post": post.serialize()
    }), 201


# ===============================
#   OBTENER PUBLICACIÓN POR ID
# ===============================
@blog.route("/<int:id>", methods=["GET"])
def get_post(id):
    post = Post.query.get(id)
    if post is None:
        return jsonify({"error": f"id {id} de la publicación no existe"}), 404
    return jsonify(post.serialize()), 200


# ===============================
#   ACTUALIZAR PUBLICACIÓN
# ===============================
@blog.route("/update/<int:id>", methods=["PUT"])
@login_required
def update(id):
    identity = get_jwt_identity()
    user_id = identity.get("id") if identity else None

    post = Post.query.get(id)
    if not post:
        return jsonify({"error": "Publicación no encontrada"}), 404
    if post.author != user_id:
        return jsonify({"error": "No tienes permiso para modificar esta publicación"}), 403

    title = request.form.get("title")
    body = request.form.get("body")
    file = request.files.get("image")

    if not title:
        return jsonify({"error": "Se requiere un título"}), 400

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        upload_path = os.path.join(current_app.root_path, 'static/uploads', filename)
        file.save(upload_path)
        post.image = filename

    post.title = title
    post.body = body

    db.session.add(post)
    db.session.commit()

    return jsonify({
        "message": "Publicación actualizada correctamente",
        "post": post.serialize()
    }), 200


# ===============================
#   ELIMINAR PUBLICACIÓN
# ===============================
@blog.route("/delete/<int:id>", methods=["DELETE"])
@login_required
def delete(id):
    identity = get_jwt_identity()
    user_id = identity.get("id") if identity else None

    post = Post.query.get(id)
    if not post:
        return jsonify({"error": "Publicación no encontrada"}), 404
    if post.author != user_id:
        return jsonify({"error": "No autorizado"}), 403

    db.session.delete(post)
    db.session.commit()

    return jsonify({"message": "Publicación eliminada correctamente"}), 200
