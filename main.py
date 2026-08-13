from flask import Flask, redirect, url_for, render_template, flash, request
from views.profile import profile 
from config import DATABASE_DATABASE_URI, MAPTILER_KEY
from db import db
from dotenv import load_dotenv
from flask_jwt_extended import JWTManager
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect, CSRFError
import os

# Blueprints
from views import profile
from views.auth import auth, api_register, api_login
from views.blog import blog
from views.posts_api import posts_api
from views.about import about
from views.contact import contact
from views.terms import terms
from views.privacy import privacy


# Cargar variables de entorno (.env)
load_dotenv()

# Inicializar Flask
app = Flask(__name__)
# Configuración de MapTiler
app.config["MAPTILER_KEY"] = os.getenv("MAPTILER_KEY", MAPTILER_KEY)
# Configuración de base de datos
app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_DATABASE_URI
# OJO: es TRACK_MODIFICATIONS (plural)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
# Secret key para sesiones
app.secret_key = os.getenv("SECRET_KEY", "dev-secret-change-me")

# JWT
app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY", "jwt-secret-change-me")
jwt = JWTManager(app)

# Proteccion CSRF para los formularios HTML (los que usan sesion + cookie).
# La API JSON queda exenta: se autentica con un header Authorization: Bearer,
# que el navegador no manda solo, asi que no es vulnerable a CSRF.
csrf = CSRFProtect(app)
csrf.exempt(posts_api)
csrf.exempt(api_register)
csrf.exempt(api_login)

# Inicializar extensiones
db.init_app(app)
migrate = Migrate(app, db)

# Registrar blueprints
app.register_blueprint(auth)
app.register_blueprint(blog)
app.register_blueprint(posts_api)
app.register_blueprint(about)
app.register_blueprint(contact)
app.register_blueprint(terms)
app.register_blueprint(privacy)
app.register_blueprint(profile)
@app.route("/")
def index():
    return render_template("home.html")


@app.errorhandler(CSRFError)
def handle_csrf_error(e):
    """El token CSRF vence junto con la sesion.

    Sin esto el usuario ve un 400 crudo de Flask; tipicamente pasa cuando deja
    el formulario abierto mucho tiempo y despues lo envia.
    """
    flash("Tu sesion expiro por seguridad. Volve a intentarlo.")
    return redirect(request.referrer or url_for("index")), 303


if __name__ == "__main__":
    # Si querés crear tablas automáticamente en desarrollo, podés descomentar esto:
    with app.app_context():
        db.create_all()
        app.run(debug=True)
