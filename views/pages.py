"""Paginas estaticas de contenido (sobre, contacto, terminos, privacidad).

Antes eran cuatro blueprints separados (about.py, contact.py, terms.py,
privacy.py), cada uno con un Blueprint, una ruta "/" y un render_template
casi identicos. Al no tener ninguna logica propia (ni formularios, ni
modelos), no habia razon para mantenerlos en cuatro archivos: se unifican en
uno solo y cada pagina es una ruta con su propio path completo, para no
cambiar las URLs existentes.
"""

from flask import Blueprint, render_template

pages = Blueprint("pages", __name__)


@pages.route("/sobre/")
def about():
    return render_template("about.html")


@pages.route("/contacto/")
def contact():
    return render_template("contact.html")


@pages.route("/terminos/")
def terms():
    return render_template("terms.html")


@pages.route("/privacidad/")
def privacy():
    return render_template("privacy.html")
