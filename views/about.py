from flask import Blueprint, render_template

about = Blueprint("about", __name__, url_prefix="/sobre")

@about.route("/")
def index():
    return render_template("about.html")
