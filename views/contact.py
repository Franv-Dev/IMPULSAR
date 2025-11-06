from flask import Blueprint, render_template

contact = Blueprint("contact", __name__, url_prefix="/contacto")

@contact.route("/")
def index():
    return render_template("contact.html")
