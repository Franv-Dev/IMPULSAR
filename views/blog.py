from flask import (
    render_template, Blueprint, redirect, flash, g, request, url_for, current_app
)
from werkzeug.exceptions import abort
from models.post import Post
from models.user import User
from views.auth import login_required
from db import db
from werkzeug.utils import secure_filename
import os

blog = Blueprint("blog", __name__, url_prefix="/blog")

# ---------------------------
# Configuración básica
# ---------------------------

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    """Verifica si un archivo tiene una extensión permitida."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


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
        abort(403)
    return post


# ---------------------------
# Rutas públicas
# ---------------------------

@blog.route("/")
def index():
    """Muestra todas las publicaciones (emprendimientos) públicas."""
    posts = Post.query.order_by(Post.created.desc()).all()
    return render_template("blog/index.html", posts=posts, get_user=get_user)


# ---------------------------
# Rutas privadas (usuario logueado)
# ---------------------------

@blog.route("/mis-emprendimientos")
@login_required
def my_posts():
    """Listado de emprendimientos creados por el usuario actual."""
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
        title = request.form.get("title")
        body = request.form.get("body")
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
                filename = secure_filename(file.filename)
                upload_path = os.path.join(current_app.root_path, "static/uploads", filename)
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
    post = get_post(id)

    if request.method == "POST":
        post.title = request.form.get("title")
        post.body = request.form.get("body")
        file = request.files.get("image")

        error = None
        if not post.title:
            error = "Se requiere un título."

        # Si hay imagen nueva, reemplazarla
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(current_app.root_path, "static/uploads", filename))
            post.image = filename

        if error:
            flash(error)
        else:
            db.session.add(post)
            db.session.commit()
            flash("Emprendimiento actualizado.")
            return redirect(url_for("blog.my_posts"))

    return render_template("blog/update.html", post=post)


@blog.route("/delete/<int:id>")
@login_required
def delete(id):
    """Eliminar un emprendimiento."""
    post = get_post(id)
    db.session.delete(post)
    db.session.commit()
    flash("Emprendimiento eliminado.")
    return redirect(url_for("blog.my_posts"))
