from flask import (
    render_template, Blueprint, redirect, flash, g, request, url_for, current_app
)
from werkzeug.exceptions import abort
from models.post import Post
from models.user import User
from views.auth import login_required
from db import db
from werkzeug.utils import secure_filename
import os, uuid
from models.review import Review
from sqlalchemy import func


blog = Blueprint("blog", __name__, url_prefix="/blog")

# ---------------------------
# Configuración
# ---------------------------

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}

def allowed_file(filename):
    """Verifica si el archivo tiene una extensión permitida."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


# ---------------------------
# Utilidades
# ---------------------------

def get_user(id):
    """Obtener usuario por ID o devolver 404."""
    return User.query.get_or_404(id)

def get_post(id, check_author=True):
    """Obtener post por ID y validar autor si corresponde."""
    post = Post.query.get(id)
    if post is None:
        abort(404, f"id {id} de la publicación no existe.")
    if check_author and post.author != g.user.id:
        flash("No tenés permiso para acceder a este emprendimiento.")
        return redirect(url_for("blog.my_posts"))
    return post


# ---------------------------
# Rutas públicas
# ---------------------------

@blog.route("/")
def index():
    """Lista pública de emprendimientos."""
    posts = Post.query.order_by(Post.created.desc()).all()
    return render_template("blog/index.html", posts=posts, get_user=get_user)
@blog.route("/<int:id>")
def detail(id):
    """Detalle de un emprendimiento + reseñas."""
    post = Post.query.get_or_404(id)

    reviews = (
        Review.query
        .filter_by(post_id=id)
        .order_by(Review.created.desc())
        .all()
    )

    avg_rating = (
        db.session.query(func.avg(Review.rating))
        .filter(Review.post_id == id)
        .scalar()
    )
    # Redondeo simple a 1 decimal
    avg_rating = round(avg_rating, 1) if avg_rating else None

    return render_template(
        "blog/detail.html",
        post=post,
        reviews=reviews,
        avg_rating=avg_rating
    )

# ---------------------------
# Rutas privadas (usuario logueado)
# ---------------------------

@blog.route("/mis-emprendimientos")
@login_required
def my_posts():
    """Listado de emprendimientos del usuario actual."""
    posts = (
        Post.query.filter_by(author=g.user.id)
        .order_by(Post.created.desc())
        .all()
    )
    return render_template("blog/my_posts.html", posts=posts)


@blog.route("/create", methods=("GET", "POST"))
@login_required
def create():
    """Registrar un nuevo emprendimiento."""
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        body = request.form.get("body", "").strip()
        file = request.files.get("image")

        error = None
        filename = None

        if not title:
            error = "Se requiere un título."
        elif not body:
            error = "Se requiere una descripción."

        # Guardar imagen si hay
        if file and file.filename != "":
            if allowed_file(file.filename):
                # Crear carpeta si no existe
                upload_dir = os.path.join(current_app.root_path, "static/uploads")
                os.makedirs(upload_dir, exist_ok=True)

                # Generar nombre único
                filename = f"{uuid.uuid4().hex[:8]}_{secure_filename(file.filename)}"
                upload_path = os.path.join(upload_dir, filename)
                file.save(upload_path)
            else:
                error = "Formato de imagen no permitido (usa png, jpg, jpeg o gif)."

        if error:
            flash(error)
        else:
            post = Post(author=g.user.id, title=title, body=body, image=filename)
            db.session.add(post)
            db.session.commit()
            flash("Emprendimiento registrado correctamente.")
            return redirect(url_for("blog.my_posts"))

    return render_template("blog/create.html")


@blog.route("/update/<int:id>", methods=("GET", "POST"))
@login_required
def update(id):
    """Actualizar emprendimiento existente."""
    post = Post.query.get_or_404(id)
    if post.author != g.user.id:
        flash("No tenés permiso para editar este emprendimiento.")
        return redirect(url_for("blog.my_posts"))

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        body = request.form.get("body", "").strip()
        file = request.files.get("image")

        error = None
        if not title:
            error = "Se requiere un título."

        # Imagen nueva
        if file and file.filename != "":
            if allowed_file(file.filename):
                upload_dir = os.path.join(current_app.root_path, "static/uploads")
                os.makedirs(upload_dir, exist_ok=True)
                filename = f"{uuid.uuid4().hex[:8]}_{secure_filename(file.filename)}"
                upload_path = os.path.join(upload_dir, filename)
                file.save(upload_path)
                post.image = filename
            else:
                error = "Formato de imagen no permitido (usa png, jpg, jpeg o gif)."

        if error:
            flash(error)
        else:
            post.title = title
            post.body = body
            db.session.commit()
            flash("Emprendimiento actualizado correctamente.")
            return redirect(url_for("blog.my_posts"))

    return render_template("blog/update.html", post=post)


@blog.route("/delete/<int:id>")
@login_required
def delete(id):
    """Eliminar emprendimiento."""
    post = Post.query.get_or_404(id)
    if post.author != g.user.id:
        flash("No tenés permiso para eliminar este emprendimiento.")
        return redirect(url_for("blog.my_posts"))

    try:
        db.session.delete(post)
        db.session.commit()
        flash("Emprendimiento eliminado correctamente.")
    except Exception as e:
        db.session.rollback()
        flash("Error al eliminar el emprendimiento.")
    return redirect(url_for("blog.my_posts"))

@blog.route("/<int:id>/review", methods=["POST"])
@login_required
def add_review(id):
    """Agregar una reseña (rating + comentario) a un emprendimiento."""
    post = Post.query.get_or_404(id)

    # No permitir que el autor se reseñe a sí mismo
    if post.author == g.user.id:
        flash("No podés dejar una reseña sobre tu propio emprendimiento.")
        return redirect(url_for("blog.detail", id=id))

    try:
        rating = int(request.form.get("rating", 0))
    except ValueError:
        rating = 0

    comment = (request.form.get("comment") or "").strip()

    error = None
    if rating < 1 or rating > 5:
        error = "Seleccioná una calificación entre 1 y 5 estrellas."

    if error:
        flash(error)
    else:
        review = Review(
            post_id=id,
            user_id=g.user.id,
            rating=rating,
            comment=comment
        )
        db.session.add(review)
        db.session.commit()
        flash("¡Gracias por tu reseña!")

    return redirect(url_for("blog.detail", id=id))
