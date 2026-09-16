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

from flask import Flask, flash, g, redirect, render_template, request, url_for
from flask_jwt_extended import JWTManager
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFError, CSRFProtect
from werkzeug.exceptions import RequestEntityTooLarge
from werkzeug.middleware.proxy_fix import ProxyFix

from config import get_config
from db import db
from services import seguridad
from services.eventos import (
    dia_semana_corto, formatear_fecha, mes_corto, parsear_fecha,
)
from services.formatting import render_biography, tiempo_relativo
from services.horarios import formatear as formatear_hora
from services.notificaciones_email import mail
from services.precios import formatear as formatear_precio
from services.precios import texto_para_formulario as precio_para_formulario
from services.uploads import MAX_IMAGE_BYTES

# Blueprints. Los dominios ya migrados a app/ exponen el suyo en vistas.py, que
# es de donde se pide: ninguno reexporta desde su __init__, para no meter las
# vistas en el medio de cada import de sus modelos (ver app/blog/__init__.py).
# Los que todavia no se migraron siguen en views/.
from app.blog import consultas as consultas_blog
from app.blog import reglas as reglas_blog
from app.blog.modelo_post import Categorias, Post
from app.blog.vistas import blog
from app.panel.vistas import panel
from app.oportunidades.vistas import oportunidades
from app.personal.vistas import personal
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

    _confiar_en_el_proxy(app)
    _registrar_extensiones(app)
    _registrar_cabeceras_de_seguridad(app)
    _registrar_blueprints(app)
    _registrar_rutas(app)
    _registrar_manejadores_de_error(app)
    _registrar_filtros_jinja(app)

    return app


def _confiar_en_el_proxy(app):
    """Hace que request.remote_addr sea la IP de quien entra y no la del proxy.

    Solo si PROXY_FIX_X_FOR dice cuantos proxies hay adelante (ver config.py,
    que explica por que el default es cero y por que el limite por IP del login
    depende de esto). Sin proxy declarado la app queda exactamente como estaba.
    """
    saltos = app.config.get("PROXY_FIX_X_FOR", 0)
    if not saltos:
        return

    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=saltos, x_proto=saltos)


def _registrar_extensiones(app):
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    csrf.init_app(app)
    # El correo saliente de las notificaciones (ver
    # services/notificaciones_email.py). Se enlaza siempre, aunque no haya
    # credenciales: sin ellas la app arranca igual y los avisos no se mandan,
    # que es lo que pasa en los tests y en una copia local recien clonada.
    mail.init_app(app)

    # La API JSON queda exenta de CSRF: se autentica con el header
    # Authorization, que el navegador no manda solo, asi que no es vulnerable
    # a CSRF. Exigirle token romperia a cualquier cliente de la API.
    csrf.exempt(posts_api)
    csrf.exempt(api_register)
    csrf.exempt(api_login)


def _registrar_cabeceras_de_seguridad(app):
    """CSP y companiia en toda respuesta (ver services/seguridad.py).

    Va como after_request y no como middleware WSGI para que alcance tambien a
    las paginas de error y a los archivos de static/, que son respuestas de
    Flask igual que cualquier otra.
    """

    @app.before_request
    def renovar_nonce():
        """Un nonce nuevo por request, y no uno perezoso la primera vez que lo piden.

        La diferencia importa porque `g` cuelga del contexto de APLICACION, no
        del de request: si hay uno empujado desde afuera (los tests lo hacen, y
        cualquier codigo que atienda requests con un app_context abierto
        tambien), Flask no empuja otro por request y `g` sobrevive de una a la
        siguiente. Con un nonce perezoso eso significa el MISMO nonce para
        muchas respuestas, que es tanto como no tener nonce: al atacante le
        alcanza con leerlo una vez para que su <script> inyectado pase.
        """
        g.csp_nonce = seguridad.nonce_nuevo()

    def csp_nonce():
        """El nonce de ESTA respuesta, para escribirlo en el <script>.

        Se lee de g y no se genera aca: el template lo pide una vez por
        <script>, y todos tienen que traer el mismo valor que la cabecera de la
        respuesta que los lleva.
        """
        if not hasattr(g, "csp_nonce"):
            # Sin request de por medio (un render suelto en un script): el
            # nonce no sirve de nada, pero tampoco puede reventar el template.
            g.csp_nonce = seguridad.nonce_nuevo()
        return g.csp_nonce

    # Como global de Jinja y no como variable de contexto: lo usa base.html,
    # que renderiza en todas las pantallas, y pasarlo desde cada vista seria
    # olvidarselo en la proxima.
    app.jinja_env.globals["csp_nonce"] = csp_nonce

    @app.after_request
    def poner_cabeceras(respuesta):
        # setdefault y no asignacion: si alguna vista alguna vez necesita una
        # politica propia, la suya gana y esto no se la pisa.
        for nombre, valor in seguridad.CABECERAS_FIJAS.items():
            respuesta.headers.setdefault(nombre, valor)
        respuesta.headers.setdefault(
            "Content-Security-Policy", seguridad.politica_csp(csp_nonce())
        )
        return respuesta


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
    app.register_blueprint(panel)
    app.register_blueprint(personal)
    app.register_blueprint(oportunidades)
    app.register_blueprint(admin)


def _registrar_rutas(app):
    @app.route("/")
    def index():
        # Los 7 rubros salen del mismo lugar que el <select> del listado
        # (Categorias.ETIQUETAS), asi que agregar uno nuevo lo hace aparecer en
        # los dos lados sin tocar el template.
        #
        # El conteo es un COUNT, no un len() del listado: la grilla de abajo
        # trae solo una pagina, y el numero del titulo habla de la plataforma
        # entera. Sigue siendo de toda la plataforma y no de una ciudad: Post
        # no tiene localidad, solo una direccion en texto libre.
        #
        # El de cada rubro sale de la misma consulta agrupada que ya usa la
        # columna de filtros del listado, no de siete COUNT.
        return render_template(
            "home.html",
            categorias=Categorias.ETIQUETAS,
            # Sin borradores, igual que la grilla de abajo y que el
            # numero de cada rubro: es el tamaño de la plataforma que se puede
            # visitar, no el de la tabla.
            total_posts=reglas_blog.solo_publicados(Post.query).count(),
            conteo_por_rubro=consultas_blog.conteo_por_categoria(),
        )


def _registrar_filtros_jinja(app):
    # Convierte **negrita**, [links](url) y saltos de linea de la bio en HTML
    # seguro (ver services/formatting.py). Se registra como filtro para no
    # tener que importarlo en cada vista que renderiza una biografia.
    app.jinja_env.filters["render_bio"] = render_biography
    # "hace 2 semanas". Fecha las resenias de la ficha: leyendo una resenia
    # lo que importa es si es de esta temporada o de hace dos anios, no el
    # dia exacto (que igual queda en el title del elemento).
    app.jinja_env.filters["hace"] = tiempo_relativo
    # "13 de septiembre de 2026". Se registra como filtro por lo mismo que
    # render_bio: lo usan el perfil y la cartelera, y asi no hay que pasarlo
    # como variable de contexto desde cada vista.
    app.jinja_env.filters["fecha_evento"] = formatear_fecha
    app.jinja_env.filters["mes_corto"] = mes_corto
    app.jinja_env.filters["dia_semana_corto"] = dia_semana_corto
    # "09:30". El mismo formateo de hora que ya usaba el perfil, ahora tambien
    # en las tres pantallas de turnos, que muestran horas en cada fila. Filtro
    # y no strftime en la plantilla: strftime("%H:%M") repetido veinte veces es
    # el formato escrito veinte veces, y ademas devuelve "" con una hora vacia
    # en vez de reventar.
    app.jinja_env.filters["hora"] = formatear_hora
    # "2026-09-13" -> date, para la vista previa del formulario de evento,
    # que trabaja sobre el texto crudo que mando el usuario. Devuelve None
    # si esta vacio o mal escrito, y la plantilla ya pregunta antes de usarlo.
    app.jinja_env.filters["fecha_desde_iso"] = parsear_fecha
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
        # Los rubros van a la plantilla porque el 404 dejo de ser un cartel y
        # pasa a ser una bifurcacion: casi siempre se llega desde un
        # emprendimiento dado de baja o un link viejo, y la persona venia a
        # buscar algo. Es el mismo Categorias.ETIQUETAS del listado, no una
        # lista propia de esta pantalla.
        return render_template("errors/404.html", categorias=Categorias.ETIQUETAS), 404

    @app.errorhandler(500)
    def manejar_error_interno(e):
        db.session.rollback()
        app.logger.exception("Error interno no controlado")
        return render_template("errors/500.html"), 500


if __name__ == "__main__":
    app = create_app()
    app.run(debug=app.config.get("DEBUG", False))
