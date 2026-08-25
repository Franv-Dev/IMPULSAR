"""Punto de entrada de IMPULSAR.

Usa el patron "application factory": en vez de crear la app cuando se importa
el modulo, la crea una funcion. Esto permite levantar varias apps con distinta
configuracion (por ejemplo una con MySQL para uso real y otra con SQLite en
memoria para los tests) sin duplicar el armado ni depender de variables
globales.

Como correrlo:
    flask --app wsgi run          (ver wsgi.py, el entrypoint estable)
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
from services.eventos import formatear_fecha, mes_corto
from services.formatting import render_biography
from services.precios import formatear as formatear_precio
from services.precios import texto_para_formulario as precio_para_formulario
from services.uploads import MAX_IMAGE_BYTES

# Blueprints. Los dominios ya migrados a app/ exponen el suyo en vistas.py, que
# es de donde se pide: ninguno reexporta desde su __init__, para no meter las
# vistas en el medio de cada import de sus modelos (ver app/blog/__init__.py).
# Los que todavia no se migraron siguen en views/.
from app.blog.vistas import blog
from app.perfil.vistas import profile
from app.servicios.vistas import servicios
from app.turnos.vistas import turnos
from views.admin import admin
from views.auth import api_login, api_register, auth
from views.eventos import eventos
from views.eventos_api import eventos_api
from views.messages import messages
from views.pages import pages
from views.posts_api import posts_api
from views.products import products

# Extensiones. Se crean vacias aca y se enlazan a la app dentro de create_app,
# que es lo que permite tener mas de una app conviviendo.
migrate = Migrate()
jwt = JWTManager()
csrf = CSRFProtect()


def create_app(config_name=None):
    """Crea y configura una instancia de la aplicacion."""
    config_class = get_config(config_name)

    # static/ y templates/ se pasan explicitos, con la ruta absoluta que calcula
    # config.py desde la raiz del repo. Por defecto Flask los busca al lado del
    # modulo que crea la app, asi que sin esto mudar este archivo a un paquete
    # dejaria las plantillas y las imagenes subidas fuera de alcance.
    app = Flask(
        __name__,
        static_folder=config_class.STATIC_FOLDER,
        template_folder=config_class.TEMPLATES_FOLDER,
    )

    app.config.from_object(config_class)
    config_class.init_app(app)

    _registrar_extensiones(app)
    _registrar_blueprints(app)
    _registrar_rutas(app)
    _registrar_manejadores_de_error(app)
    _registrar_filtros_jinja(app)

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
    app.register_blueprint(eventos)
    app.register_blueprint(eventos_api)
    app.register_blueprint(posts_api)
    app.register_blueprint(products)
    app.register_blueprint(servicios)
    app.register_blueprint(turnos)
    app.register_blueprint(pages)
    app.register_blueprint(profile)
    app.register_blueprint(messages)
    app.register_blueprint(admin)


def _registrar_rutas(app):
    @app.route("/")
    def index():
        return render_template("home.html")


def _registrar_filtros_jinja(app):
    # Convierte **negrita**, [links](url) y saltos de linea de la bio en HTML
    # seguro (ver services/formatting.py). Se registra como filtro para no
    # tener que importarlo en cada vista que renderiza una biografia.
    app.jinja_env.filters["render_bio"] = render_biography
    # "13 de septiembre de 2026". Se registra como filtro por lo mismo que
    # render_bio: lo usan el perfil y la cartelera, y asi no hay que pasarlo
    # como variable de contexto desde cada vista.
    app.jinja_env.filters["fecha_evento"] = formatear_fecha
    app.jinja_env.filters["mes_corto"] = mes_corto
    # "$ 1.500,50", con los separadores de aca (ver services/precios.py).
    # Filtro y no property del modelo: como mostrar un precio es de la
    # vista, y asi lo usan igual el catalogo y el panel.
    app.jinja_env.filters["precio"] = formatear_precio
    # El mismo precio pero como se precarga en un <input> ("1500.50"). Va como
    # filtro porque hay un formulario que se arma sin pasar por una vista que
    # prepare los datos: el de la respuesta a una solicitud, que vive adentro
    # de la pagina de la solicitud (ver app/servicios/templates/).
    app.jinja_env.filters["precio_form"] = precio_para_formulario


def _registrar_manejadores_de_error(app):
    @app.errorhandler(RequestEntityTooLarge)
    def manejar_archivo_muy_grande(e):
        # Sigue haciendo falta, pero ahora es el caso raro y no el de todos los
        # dias: desde que MAX_IMAGE_BYTES son 15 MB, una foto de celular entra y
        # la comprime save_post_image. Aca caen las que ni con eso entran.
        #
        # El texto no cambia porque sigue siendo exacto: dice cual es el maximo y
        # lo saca de la constante, asi que no se desincroniza si el numero se
        # vuelve a mover.
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
