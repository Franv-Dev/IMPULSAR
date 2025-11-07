from flask import (
    render_template, Blueprint, redirect, flash, g, request, url_for, current_app
)
from werkzeug.exceptions import abort

from models.user import User
from views.auth import login_required
from db import db
import os

profile = Blueprint("profile", __name__, url_prefix="/perfil")

@profile.route("/<int:user_id>")
def view_profile(user_id):
    user = User.query.get_or_404(user_id)
    return render_template(
        "profile.html",
        user=user,
        MAPTILER_KEY=current_app.config["MAPTILER_KEY"]
    )

@profile.route("/create", methods=("GET", "POST"))
@login_required
def create():
    """Permite al usuario logueado crear o actualizar su biografía"""
    if request.method == "POST":
        biography = request.form.get("body", "").strip()
        if not biography:
            flash("Se requiere una biografía.")
        else:
            # Actualizar el campo de biografía del usuario logueado
            g.user.biography = biography
            db.session.commit()
            flash("Biografía actualizada con éxito.")
            return redirect(url_for("profile.view_profile", user_id=g.user.id))

    return render_template("profile/create_bio.html")