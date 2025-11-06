from flask import Blueprint, render_template

terms = Blueprint("terms", __name__, url_prefix="/terminos")

@terms.route("/")
def index():
    return render_template("terms.html")
