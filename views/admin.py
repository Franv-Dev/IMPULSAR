"""Panel de administrador: usuarios, moderacion de emprendimientos y metricas.

Vista simple pensada para el rol admin: no hay nada de esto en la API JSON,
solo paginas HTML protegidas con @admin_required (ver views/auth.py).
"""

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from sqlalchemy import func

from db import db
from models.post import Post
from models.review import Review
from models.user import Roles, User
from views.auth import admin_required

admin = Blueprint("admin", __name__, url_prefix="/admin")


@admin.route("/")
@admin_required
def dashboard():
    """Metricas basicas de la plataforma."""
    metricas = {
        "usuarios": db.session.query(func.count(User.id)).scalar() or 0,
        "posts": db.session.query(func.count(Post.id)).scalar() or 0,
        "resenias": db.session.query(func.count(Review.id)).scalar() or 0,
    }
    return render_template("admin/dashboard.html", metricas=metricas)


@admin.route("/usuarios")
@admin_required
def usuarios():
    """Listado de usuarios, con accion para banear/desbanear."""
    lista = User.query.order_by(User.username.asc()).all()
    return render_template("admin/usuarios.html", usuarios=lista, Roles=Roles)


@admin.route("/usuarios/<int:user_id>/ban", methods=["POST"])
@admin_required
def toggle_ban(user_id):
    """Banea o desbanea (toggle) a un usuario. No se puede banear a otro admin."""
    usuario = User.query.get_or_404(user_id)

    if usuario.rol == Roles.ADMIN:
        flash("No podés banear a otro administrador.")
        return redirect(url_for("admin.usuarios"))

    usuario.is_banned = not usuario.is_banned
    db.session.commit()
    flash(f"{'Baneado' if usuario.is_banned else 'Desbaneado'}: {usuario.username}.")
    return redirect(url_for("admin.usuarios"))


@admin.route("/emprendimientos")
@admin_required
def emprendimientos():
    """Listado de todos los emprendimientos, para moderacion."""
    paginacion = (
        Post.query
        .order_by(Post.created.desc())
        .paginate(
            page=request.args.get("page", 1, type=int),
            per_page=20,
            error_out=False,
        )
    )
    return render_template("admin/emprendimientos.html", paginacion=paginacion)


@admin.route("/emprendimientos/<int:post_id>/eliminar", methods=["POST"])
@admin_required
def delete_post(post_id):
    """Eliminar cualquier emprendimiento (moderacion), sin importar el dueño."""
    post = Post.query.get_or_404(post_id)
    titulo = post.title

    try:
        db.session.delete(post)
        db.session.commit()
        flash(f"Se eliminó el emprendimiento «{titulo}».")
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Error al eliminar el post %s desde el panel de admin", post_id)
        flash("Error al eliminar el emprendimiento.")

    return redirect(url_for("admin.emprendimientos"))
