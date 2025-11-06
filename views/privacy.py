from flask import Blueprint, render_template

privacy = Blueprint("privacy", __name__, url_prefix="/privacidad")

@privacy.route("/")
def index():
    return render_template("privacy.html")
