"""Punto de entrada de IMPULSAR.

Usa el patron "application factory": en vez de crear la app cuando se importa
el modulo, la crea una funcion. Esto permite levantar varias apps con distinta
configuracion (por ejemplo una con MySQL para uso real y otra con SQLite en
memoria para los tests) sin duplicar el armado ni depender de variables
globales.

Como correrlo:
    flask --app main run          (Flask detecta create_app automaticamente)
    python main.py                (equivalente, para desarrollo)
"""

import os

from flask import Flask, flash, redirect, render_template, request, url_for
from flask_jwt_extended import JWTManager
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFError, CSRFProtect
from werkzeug.exceptions import RequestEntityTooLarge

from config import get_config
from db import db
from services.uploads import MAX_IMAGE_BYTES

# Blueprints
from views.auth import api_login, api_register, auth
from views.blog import blog
from views.pages import pages
from views.posts_api import posts_api
from views.profile import profile

# Extensiones. Se crean vacias aca y se enlazan a la app dentro de create_app,
# que es lo que permite tener mas de una app conviviendo.
migrate = Migrate()
jwt = JWTManager()
csrf = CSRFProtect()


def create_app(config_name=None):
    """Crea y configura una instancia de la aplicacion."""
    app = Flask(__name__)

    config_class = get_config(config_name)
    app.config.from_object(config_class)
    config_class.init_app(app)

    _registrar_extensiones(app)
    _registrar_blueprints(app)
    _registrar_rutas(app)
    _registrar_manejadores_de_error(app)

    return app


def _registrar_extensiones(app):
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    csrf.init_app(app)

    # La API JSON queda exenta de CSRF: se autentica con el header
    # Authorization, que el navegador no manda solo, asi que no es vulnerable
    # a CSRF. Exigirle token romperia a cualquier cliente de la API.
    csrf.exempt(posts_api)
    csrf.exempt(api_register)
    csrf.exempt(api_login)


def _registrar_blueprints(app):
    app.register_blueprint(auth)
    app.register_blueprint(blog)
    app.register_blueprint(posts_api)
    app.register_blueprint(pages)
    app.register_blueprint(profile)


def _registrar_rutas(app):
    @app.route("/")
    def index():
        return render_template("home.html")


def _registrar_manejadores_de_error(app):
    @app.errorhandler(RequestEntityTooLarge)
    def manejar_archivo_muy_grande(e):
        limite_mb = MAX_IMAGE_BYTES // (1024 * 1024)
        flash(f"La imagen es demasiado grande. El máximo permitido es {limite_mb} MB.")
        return redirect(request.referrer or url_for("index")), 303

    @app.errorhandler(CSRFError)
    def manejar_error_csrf(e):
        # El token vence junto con la sesion: pasa cuando el usuario deja el
        # formulario abierto mucho tiempo. Sin esto veria un 400 crudo.
        flash("Tu sesión expiró por seguridad. Volvé a intentarlo.")
        return redirect(request.referrer or url_for("index")), 303

    @app.errorhandler(404)
    def manejar_no_encontrado(e):
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def manejar_error_interno(e):
        db.session.rollback()
        app.logger.exception("Error interno no controlado")
        return render_template("errors/500.html"), 500


if __name__ == "__main__":
    app = create_app()
    app.run(debug=app.config.get("DEBUG", False))
