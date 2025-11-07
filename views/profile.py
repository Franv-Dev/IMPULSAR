from flask import Blueprint, render_template
from models.user import User

profile = Blueprint("profile", __name__, url_prefix="/perfil")

@profile.route("/<int:user_id>")
def view_profile(user_id):
    user = User.query.get_or_404(user_id)
    return render_template("profile.html", user=user)
